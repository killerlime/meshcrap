package org.jkmesh.survey;

import android.Manifest;
import android.app.*;
import android.bluetooth.*;
import android.content.*;
import android.content.pm.PackageManager;
import android.location.*;
import android.os.*;
import com.google.protobuf.ByteString;
import org.meshtastic.proto.MeshProtos;
import org.meshtastic.proto.Portnums;
import org.json.*;
import java.util.*;
import java.util.concurrent.*;
import java.net.*;
import java.nio.charset.StandardCharsets;

public final class SurveyService extends Service implements MeshBle.Listener {
    static SurveyService instance;
    static String summary="Disconnected. Pair with the collector, then connect a radio.";
    final Map<Integer,String> channels=new HashMap<>();
    double radius=10;
    private final Handler h=new Handler(Looper.getMainLooper());
    private final ExecutorService network=Executors.newSingleThreadExecutor();
    private final Map<Integer,MeshProtos.NodeInfo> nodes=new HashMap<>();
    private final LinkedHashMap<Integer,Attempt> attempts=new LinkedHashMap<>();
    private final Set<Integer> tried=new HashSet<>();
    private MeshBle ble;private Outbox outbox;private LocationManager locations;private Location phoneLocation;
    private boolean ready=false,armed=false,verified=false,disposed=false,syncing=false;
    private int own=0,channel=0,nonce;private long survey=0,leaseUntil=0,lastSent=0,lastSync=0,lastLocation=0,lastHeartbeat=0,connectedAt=0;
    private String nodePrefix="my";
    private String area="",message="Connecting…",endpoint,token;private Attempt pending;
    private volatile HttpURLConnection connection;
    static final class Target {final int number;final double distance;final String label;Target(int n,double d,String label){number=n;distance=d;this.label=label;}}
    private static final class Attempt {
        int packet,dest,source,channel;long survey,at,elapsed;boolean test,done;JSONObject position;
    }
    private long clock(){return SystemClock.elapsedRealtime();}
    private static long epoch(){return System.currentTimeMillis()/1000;}
    private static long unsigned(int n){return Integer.toUnsignedLong(n);}
    private static String id(int n){return String.format(Locale.ROOT,"!%08x",n);}
    private String name(int n){MeshProtos.NodeInfo info=nodes.get(n);return info!=null&&!info.getUser().getLongName().isEmpty()?info.getUser().getLongName():id(n);}
    private boolean isJk(){MeshProtos.NodeInfo info=nodes.get(own);return info!=null&&(info.getUser().getShortName().trim().toLowerCase(Locale.ROOT).startsWith(nodePrefix)||info.getUser().getLongName().trim().toLowerCase(Locale.ROOT).startsWith(nodePrefix+" "));}
    public IBinder onBind(Intent i){return null;}
    public void onCreate(){super.onCreate();instance=this;outbox=new Outbox(this);
        NotificationManager manager=getSystemService(NotificationManager.class);manager.createNotificationChannel(new NotificationChannel("survey","Survey connection",NotificationManager.IMPORTANCE_LOW));
    }
    @android.annotation.SuppressLint("MissingPermission") public int onStartCommand(Intent intent,int flags,int startId){
        if(intent==null){stopSelf();return START_NOT_STICKY;}
        if("pause".equals(intent.getAction())){pause("Paused from notification");return START_NOT_STICKY;}
        if("stop".equals(intent.getAction())){stopSelf();return START_NOT_STICKY;}
        if(ble!=null)return START_NOT_STICKY;
        if(Build.VERSION.SDK_INT>=29){
            int types=android.content.pm.ServiceInfo.FOREGROUND_SERVICE_TYPE_CONNECTED_DEVICE;
            if(checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION)==PackageManager.PERMISSION_GRANTED)types|=android.content.pm.ServiceInfo.FOREGROUND_SERVICE_TYPE_LOCATION;
            startForeground(1,notification(),types);
        }else startForeground(1,notification());
        try{
            JSONObject setup=new JSONObject(PrivateStore.read(this));endpoint=setup.getString("url");token=setup.getString("token");nodePrefix=setup.getString("node_prefix").trim().toLowerCase(Locale.ROOT);if(!nodePrefix.matches("[a-z][a-z0-9]{0,7}"))throw new IllegalArgumentException("Invalid node prefix");
            BluetoothAdapter adapter=getSystemService(BluetoothManager.class).getAdapter();
            if(adapter==null||!adapter.isEnabled())throw new IllegalStateException("Turn Bluetooth on first");
            nonce=new java.security.SecureRandom().nextInt();if(nonce==0)nonce=1;
            if(epoch()-getSharedPreferences("cadence",0).getLong("last_sent",0)<120)lastSent=clock();
            connectedAt=clock();ble=new MeshBle(this,adapter.getRemoteDevice(intent.getStringExtra("mac")),h,this);
            locations=getSystemService(LocationManager.class);
            if(checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION)==PackageManager.PERMISSION_GRANTED){
                if(locations.isProviderEnabled(LocationManager.GPS_PROVIDER))locations.requestLocationUpdates(LocationManager.GPS_PROVIDER,10000,5,locationListener);
                if(locations.isProviderEnabled(LocationManager.NETWORK_PROVIDER))locations.requestLocationUpdates(LocationManager.NETWORK_PROVIDER,10000,5,locationListener);
            }
            h.post(tick);
        }catch(Exception e){message="Could not start: "+e.getClass().getSimpleName()+". Check Bluetooth and pairing.";summary=message;stopSelf();}
        return START_NOT_STICKY;
    }
    private Notification notification(){
        PendingIntent open=PendingIntent.getActivity(this,0,new Intent(this,MainActivity.class),PendingIntent.FLAG_IMMUTABLE|PendingIntent.FLAG_UPDATE_CURRENT);
        PendingIntent pause=PendingIntent.getService(this,1,new Intent(this,SurveyService.class).setAction("pause"),PendingIntent.FLAG_IMMUTABLE|PendingIntent.FLAG_UPDATE_CURRENT);
        PendingIntent stop=PendingIntent.getService(this,2,new Intent(this,SurveyService.class).setAction("stop"),PendingIntent.FLAG_IMMUTABLE|PendingIntent.FLAG_UPDATE_CURRENT);
        return new Notification.Builder(this,"survey").setSmallIcon(android.R.drawable.ic_menu_mylocation).setContentTitle("Meshcrap Survey · "+(armed?"automatic requests enabled":"requests paused"))
            .setContentText(own==0?"Connecting to selected radio":name(own)+" · "+id(own)).setContentIntent(open).setOngoing(true)
            .addAction(new Notification.Action.Builder(null,"Pause",pause).build()).addAction(new Notification.Action.Builder(null,"Stop",stop).build()).build();
    }
    private void notifyState(){getSystemService(NotificationManager.class).notify(1,notification());}
    void pause(String reason){armed=false;message=reason;notifyState();}
    void chooseChannel(int n){if(pending!=null){message="Wait for the outstanding traceroute before changing channel";return;}if(channels.containsKey(n)){channel=n;verified=false;pause("Channel changed. Run one successful test before enabling automatic requests.");}}
    String arm(){if(!verified)return "A successful one-time traceroute on this connection and channel is required first.";
        if(!ready||!isJk()||survey==0||clock()>=leaseUntil)return "Connect a local node and start a survey on the website with a live collector connection.";
        if(position()==null)return "Waiting for a recent accurate position.";
        armed=true;message="Nearby nodes will be tried one at a time";notifyState();return message;
    }
    public void ready(){ble.send(MeshProtos.ToRadio.newBuilder().setWantConfigId(nonce).build().toByteArray());message="Reading node and channel configuration…";}
    public void failed(String reason){ready=false;verified=false;pause(reason);if(pending!=null){result(pending,"transport_error",null);pending=null;}}
    public void received(byte[] raw){try{
        MeshProtos.FromRadio from=MeshProtos.FromRadio.parseFrom(raw);
        if(from.hasMyInfo()){
            int number=from.getMyInfo().getMyNodeNum();if(own!=0&&number!=own){ready=false;pause("Source radio changed. Stop and reconnect to verify it.");return;}own=number;
            tried.clear();for(String saved:getSharedPreferences("cadence",0).getStringSet("tried_"+own+"_"+survey,Collections.emptySet()))tried.add(Integer.parseInt(saved));
        }
        if(from.hasNodeInfo())nodes.put(from.getNodeInfo().getNum(),from.getNodeInfo());
        if(from.hasChannel()){
            var c=from.getChannel();
            if(ready){verified=false;pause("Channel configuration changed. Verify another test before resuming.");}
            if(c.getRoleValue()!=0){String n=c.getSettings().getName();channels.put(c.getIndex(),n.isEmpty()?"Unnamed "+c.getRole().name():n);}else channels.remove(c.getIndex());
        }
        if(from.getConfigCompleteId()==nonce){ready=SurveyRules.validId(unsigned(own))&&isJk()&&!channels.isEmpty();message=ready?"Connected. Confirm the displayed local node and channel, then start a survey on the website.":"This radio is not identified as a local node, or its configuration is incomplete.";notifyState();}
        if(from.getRebooted()){ready=false;verified=false;pause("Radio restarted. Stop and reconnect.");}
        if(from.hasPacket())packet(from.getPacket());
    }catch(Exception e){pause("Could not decode a radio message; reconnect before continuing.");ready=false;}}
    private void packet(MeshProtos.MeshPacket p)throws Exception {
        int n=p.getFrom();long now=epoch();
        MeshProtos.NodeInfo.Builder node=nodes.containsKey(n)?nodes.get(n).toBuilder():MeshProtos.NodeInfo.newBuilder().setNum(n);
        node.setLastHeard((int)now);
        if(p.hasDecoded()){
            var data=p.getDecoded();
            if(data.getPortnum()==Portnums.PortNum.POSITION_APP)node.setPosition(MeshProtos.Position.parseFrom(data.getPayload()));
            if(data.getPortnum()==Portnums.PortNum.NODEINFO_APP)node.setUser(MeshProtos.User.parseFrom(data.getPayload()));
            nodes.put(n,node.build());
            Attempt a=attempts.get(data.getRequestId());
            if(a!=null&&p.getFrom()==a.dest&&p.getTo()==a.source&&data.getPortnum()==Portnums.PortNum.TRACEROUTE_APP){
                boolean late=a.done;
                MeshProtos.RouteDiscovery route=MeshProtos.RouteDiscovery.parseFrom(data.getPayload());
                JSONObject detail=new JSONObject().put("route",unsignedArray(route.getRouteList())).put("route_back",unsignedArray(route.getRouteBackList()))
                    .put("snr_towards_quarter_db",new JSONArray(route.getSnrTowardsList())).put("snr_back_quarter_db",new JSONArray(route.getSnrBackList()))
                    .put("response_packet_id",unsigned(p.getId())).put("response_from",unsigned(p.getFrom())).put("response_to",unsigned(p.getTo()));
                // Duplicate responses do not create more success records.
                if(!a.done||clock()-a.elapsed<=SurveyRules.TIMEOUT_MS+600000){
                    result(a,late?"late_success":"success",detail);attempts.remove(a.packet);
                    if(pending==a)pending=null;
                    if(a.test&&!late&&a.channel==channel&&a.source==own&&a.survey==survey){verified=true;message="Test returned successfully. You can enable the nearby-node survey.";}
                }
            } else if(a!=null&&data.getPortnum()==Portnums.PortNum.ROUTING_APP&&(p.getFrom()==own||p.getFrom()==a.dest)){
                MeshProtos.Routing routing=MeshProtos.Routing.parseFrom(data.getPayload());
                if(routing.getErrorReasonValue()!=0&&!a.done){result(a,"routing_error",new JSONObject().put("routing_error",routing.getErrorReason().name()));if(pending==a)pending=null;}
            }
        }
    }
    private static JSONArray unsignedArray(List<Integer> values){JSONArray a=new JSONArray();for(int v:values)a.put(unsigned(v));return a;}
    private final LocationListener locationListener=new LocationListener(){public void onLocationChanged(Location location){if(!(Build.VERSION.SDK_INT>=31?location.isMock():location.isFromMockProvider()))phoneLocation=location;}};
    private JSONObject position(){try{
        var node=nodes.get(own);if(node!=null&&node.hasPosition()){
            var p=node.getPosition();double lat=p.getLatitudeI()*1e-7,lon=p.getLongitudeI()*1e-7;
            if(SurveyRules.validPosition(lat,lon)&&SurveyRules.fresh(unsigned(p.getTime()),epoch(),300))return new JSONObject().put("lat",lat).put("lon",lon).put("time",unsigned(p.getTime())).put("source","radio_position");
        }
        if(phoneLocation!=null&&phoneLocation.hasAccuracy()&&phoneLocation.getAccuracy()<=100&&SystemClock.elapsedRealtimeNanos()-phoneLocation.getElapsedRealtimeNanos()<120_000_000_000L&&SurveyRules.validPosition(phoneLocation.getLatitude(),phoneLocation.getLongitude()))
            return new JSONObject().put("lat",phoneLocation.getLatitude()).put("lon",phoneLocation.getLongitude()).put("time",phoneLocation.getTime()/1000).put("source","phone_gps").put("accuracy_m",phoneLocation.getAccuracy());
    }catch(Exception ignored){}return null;}
    List<Target> targets(){List<Target> result=new ArrayList<>();JSONObject loc=position();if(loc==null)return result;
        for(var n:nodes.values()){
            if(n.getNum()==own||!SurveyRules.validId(unsigned(n.getNum()))||!n.hasPosition()||!SurveyRules.fresh(unsigned(n.getLastHeard()),epoch(),86400))continue;
            var p=n.getPosition();double lat=p.getLatitudeI()*1e-7,lon=p.getLongitudeI()*1e-7;
            if(!SurveyRules.validPosition(lat,lon)||!SurveyRules.fresh(unsigned(p.getTime()),epoch(),30*86400))continue;
            double miles=SurveyRules.miles(loc.optDouble("lat"),loc.optDouble("lon"),lat,lon);
            if(miles<=radius)result.add(new Target(n.getNum(),miles,name(n.getNum())+" · "+id(n.getNum())+" · "+String.format(Locale.ROOT,"%.1f mi",miles)));
        }result.sort(Comparator.comparingDouble(t->t.distance));return result;
    }
    String trace(int destination,boolean test){
        if(!SurveyRules.maySend(ready,isJk(),pending!=null,clock(),lastSent,leaseUntil,survey)||!channels.containsKey(channel))return "Not ready: check the active survey, collector connection, channel, outstanding request and two-minute spacing.";
        if(!test&&!verified)return "Run a successful test first.";
        if(targets().stream().noneMatch(t->t.number==destination))return "This destination is no longer a nearby candidate with recent position data.";
        if(outbox.count()>=9990){pause("Upload the saved results before sending more requests");return message;}
        Attempt a=new Attempt();a.packet=new java.security.SecureRandom().nextInt();if(a.packet==0)a.packet=1;
        a.source=own;a.dest=destination;a.channel=channel;a.survey=survey;a.at=epoch();a.elapsed=clock();a.test=test;a.position=position();
        MeshProtos.Data data=MeshProtos.Data.newBuilder().setPortnum(Portnums.PortNum.TRACEROUTE_APP).setPayload(ByteString.EMPTY).setWantResponse(true).build();
        MeshProtos.MeshPacket packet=MeshProtos.MeshPacket.newBuilder().setTo(destination).setId(a.packet).setChannel(channel).setHopLimit(3).setWantAck(true).setDecoded(data).build();
        try{
            // Save intent before submitting; a process restart never retries an uncertain send.
            if(!result(a,"requested",null))return "Could not save request intent; nothing was sent.";
            a.done=false;attempts.put(a.packet,a);pending=a;lastSent=clock();tried.add(destination);
            Set<String> persisted=new HashSet<>();for(int n:tried)persisted.add(Integer.toString(n));
            if(!getSharedPreferences("cadence",0).edit().putLong("last_sent",epoch()).putStringSet("tried_"+own+"_"+survey,persisted).commit()){
                result(a,"transport_error",null);pending=null;pause("Could not save request cadence; nothing was sent.");return message;
            }
            ble.send(MeshProtos.ToRadio.newBuilder().setPacket(packet).build().toByteArray());
            message="Requested traceroute to "+name(destination)+"; waiting up to five minutes.";
        }catch(Exception e){result(a,"transport_error",null);pending=null;pause("Radio request could not be submitted; no automatic retry.");}
        return message;
    }
    private boolean result(Attempt a,String status,JSONObject details){try{
        JSONObject object=new JSONObject().put("id",UUID.randomUUID().toString()).put("kind","trace").put("survey_id",a.survey).put("source",unsigned(a.source)).put("destination",unsigned(a.dest))
            .put("packet_id",unsigned(a.packet)).put("channel",a.channel).put("requested_at",a.at).put("time",epoch()).put("status",status).put("test",a.test).put("position",a.position==null?JSONObject.NULL:a.position);
        if(details!=null)object.put("details",details);
        if(!outbox.add(object)){pause("Result storage is full; upload results before continuing.");return false;}
        if(!status.equals("requested")){a.done=true;message=name(a.dest)+": "+status.replace('_',' ');}
        return true;
    }catch(Exception e){pause("Could not save a survey result. Requests paused.");return false;}}
    private final Runnable tick=new Runnable(){public void run(){if(disposed)return;
        long now=clock();
        if(!ready&&connectedAt>0&&now-connectedAt>120000&&ble!=null){ble.close();connectedAt=0;pause("Radio configuration did not finish. Stop and reconnect.");}
        if(armed&&now>=leaseUntil)pause("Collector connection expired; requests paused. Re-enable after it reconnects.");
        if(pending!=null&&now-pending.elapsed>=SurveyRules.TIMEOUT_MS){result(pending,"timeout",null);pending=null;}
        if(ready&&now-lastHeartbeat>=60000){lastHeartbeat=now;try{ble.send(MeshProtos.ToRadio.newBuilder().setHeartbeat(MeshProtos.Heartbeat.newBuilder().setNonce(1)).build().toByteArray());}catch(Exception e){failed("Bluetooth heartbeat could not be sent");}}
        if(survey>0&&ready&&now<leaseUntil&&now-lastLocation>=15000){lastLocation=now;JSONObject loc=position();if(loc!=null)try{
            outbox.add(new JSONObject().put("id",UUID.randomUUID().toString()).put("kind","position").put("survey_id",survey).put("source",unsigned(own)).put("time",epoch()).put("position",loc));
        }catch(Exception e){pause("Could not save survey location");}}
        if(!syncing&&now-lastSync>=15000){lastSync=now;sync();}
        if(armed&&pending==null&&now-lastSent>=SurveyRules.SPACING_MS){for(Target target:targets())if(!tried.contains(target.number)){trace(target.number,false);break;}}
        while(attempts.size()>32){Integer key=attempts.keySet().iterator().next();if(pending!=null&&key==pending.packet)break;attempts.remove(key);}
        summary=(ready?"Connected: ":"Radio: ")+name(own)+" "+(own==0?"":id(own))+"\nChannel "+channel+" · "+channels.getOrDefault(channel,"waiting for configuration")+
            "\n"+(survey>0?"Survey "+survey+" · "+area:"No active website survey")+"\nCollector: "+(now<leaseUntil?"connected":"offline / not yet paired")+
            "\nNearby: "+targets().size()+" within "+radius+" miles · tried "+tried.size()+"\n"+(armed?"Automatic requests enabled":"Automatic requests paused")+
            "\n"+(position()==null?"Waiting for a recent location":"Location available")+"\nSaved for upload: "+outbox.count()+"\n\n"+message;
        h.postDelayed(this,1000);
    }};
    private void sync(){syncing=true;
        try{
            JSONArray events=outbox.batch();JSONObject request=new JSONObject().put("source",unsigned(own)).put("name",name(own)).put("ready",ready).put("armed",armed).put("channel",channel).put("nearby",targets().size()).put("events",events);
            network.execute(()->{try{
                URL url=new URL(endpoint);HttpURLConnection conn=(HttpURLConnection)url.openConnection();connection=conn;
                conn.setInstanceFollowRedirects(false);conn.setConnectTimeout(10000);conn.setReadTimeout(12000);conn.setRequestMethod("POST");conn.setRequestProperty("Content-Type","application/json");conn.setRequestProperty("Authorization","Bearer "+token);conn.setDoOutput(true);
                byte[] body=request.toString().getBytes(StandardCharsets.UTF_8);conn.setFixedLengthStreamingMode(body.length);
                try(var output=conn.getOutputStream()){output.write(body);}
                if(conn.getResponseCode()!=200)throw new java.io.IOException("Collector HTTP "+conn.getResponseCode());
                byte[] bytes;try(var input=conn.getInputStream();var output=new java.io.ByteArrayOutputStream()){
                    byte[] buffer=new byte[4096];int count;
                    while((count=input.read(buffer))!=-1){if(output.size()+count>65536)throw new java.io.IOException("Response too large");output.write(buffer,0,count);}bytes=output.toByteArray();
                }
                JSONObject reply=new JSONObject(new String(bytes,StandardCharsets.UTF_8));
                h.post(()->{if(disposed)return;try{
                    outbox.acknowledge(reply.getJSONArray("accepted"));long next=reply.optLong("survey_id",0);
                    if(next!=survey){survey=next;tried.clear();
                        for(String n:getSharedPreferences("cadence",0).getStringSet("tried_"+own+"_"+survey,Collections.emptySet()))tried.add(Integer.parseInt(n));
                        armed=false;message=next>0?"Survey ready. Choose a test destination, then enable automatic requests.":"Website survey ended; no new requests.";notifyState();}
                    area=reply.optString("area_name","");leaseUntil=clock()+Math.min(SurveyRules.LEASE_MS,Math.max(0,reply.optLong("lease_seconds",0))*1000);
                }catch(Exception e){leaseUntil=0;pause("Collector response was invalid");}finally{syncing=false;}});
            }catch(Exception e){h.post(()->{if(!disposed){syncing=false;leaseUntil=0;pause("Collector unavailable. Saved results retained; check Tailscale and pairing.");}});}finally{if(connection!=null)connection.disconnect();connection=null;}});
        }catch(Exception e){syncing=false;leaseUntil=0;pause("Unable to prepare saved results for upload");}
    }
    public void onDestroy(){disposed=true;armed=false;ready=false;if(pending!=null)result(pending,"stopped",null);
        if(ble!=null)ble.close();if(locations!=null)locations.removeUpdates(locationListener);h.removeCallbacksAndMessages(null);if(connection!=null)connection.disconnect();network.shutdownNow();
        summary="Stopped. Bluetooth released. "+outbox.count()+" saved records will upload when you reconnect.";outbox.close();instance=null;stopForeground(STOP_FOREGROUND_REMOVE);super.onDestroy();
    }
}
