package org.meshcrap.survey;

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
    static final SurveyActivityLog activityLog=new SurveyActivityLog();
    private static void log(String text){activityLog.add(System.currentTimeMillis(),text);}
    static String summary="Disconnected. Pair with the collector, then connect a radio.";
    final Map<Integer,String> channels=new HashMap<>();
    double radius=25;
    private boolean receptionRecords=false;
    private final Handler h=new Handler(Looper.getMainLooper());
    private final ExecutorService network=Executors.newSingleThreadExecutor();
    private final Map<Integer,MeshProtos.NodeInfo> nodes=new HashMap<>();
    private final LinkedHashMap<Integer,Attempt> attempts=new LinkedHashMap<>();
    private final Set<Integer> tried=new HashSet<>();
    private MeshBle ble;private Outbox outbox;private LocationManager locations;private Location phoneLocation;
    private boolean ready=false,armed=false,disposed=false,syncing=false;
    private boolean collectorResponding=false,phoneControls=false;
    private final SurveyControlState controlState=new SurveyControlState();
    private int own=0,channel=0,nonce;private long survey=0,leaseUntil=0,lastSent=0,lastSync=0,lastLocation=0,lastHeartbeat=0,connectedAt=0;
    private String nodePrefix="my";
    private String area="",message="Connecting…",endpoint,token;private Attempt pending;
    private String lastAutomaticWait="",startupFailure="";
    private volatile HttpURLConnection connection;
    static final class Target {final int number;final double distance;final String label;final boolean automatic;Target(int n,double d,String label,boolean automatic){number=n;distance=d;this.label=label;this.automatic=automatic;}}
    private static final class Attempt {
        int packet,dest,source,channel;long survey,at,elapsed;boolean test,done;JSONObject position,destinationPosition;
    }
    private long clock(){return SystemClock.elapsedRealtime();}
    private static long epoch(){return System.currentTimeMillis()/1000;}
    private static long unsigned(int n){return Integer.toUnsignedLong(n);}
    private static String id(int n){return String.format(Locale.ROOT,"!%08x",n);}
    private String name(int n){MeshProtos.NodeInfo info=nodes.get(n);return info!=null&&!info.getUser().getLongName().isEmpty()?info.getUser().getLongName():id(n);}
    private boolean isLocal(){MeshProtos.NodeInfo info=nodes.get(own);return info!=null&&(info.getUser().getShortName().trim().toLowerCase(Locale.ROOT).startsWith(nodePrefix)||info.getUser().getLongName().trim().toLowerCase(Locale.ROOT).startsWith(nodePrefix+" "));}
    public IBinder onBind(Intent i){return null;}
    public void onCreate(){super.onCreate();instance=this;outbox=new Outbox(this);
        NotificationManager manager=getSystemService(NotificationManager.class);manager.createNotificationChannel(new NotificationChannel("survey","Survey connection",NotificationManager.IMPORTANCE_LOW));
    }
    @android.annotation.SuppressLint("MissingPermission") public int onStartCommand(Intent intent,int flags,int startId){
        if(intent==null){stopSelf();return START_NOT_STICKY;}
        if("pause".equals(intent.getAction())){pause("Paused from notification");return START_NOT_STICKY;}
        if("stop".equals(intent.getAction())){stopSelf();return START_NOT_STICKY;}
        if(ble!=null)return START_NOT_STICKY;
        try{
            if(Build.VERSION.SDK_INT>=29){
                int types=android.content.pm.ServiceInfo.FOREGROUND_SERVICE_TYPE_CONNECTED_DEVICE;
                if(checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION)==PackageManager.PERMISSION_GRANTED)types|=android.content.pm.ServiceInfo.FOREGROUND_SERVICE_TYPE_LOCATION;
                startForeground(1,notification(),types);
            }else startForeground(1,notification());
            var cadence=getSharedPreferences("cadence",0);
            var migration=cadence.edit();
            for(var item:SurveyRules.migrateProbeTimes(cadence.getAll()).entrySet())migration.putLong(item.getKey(),item.getValue());
            if(!migration.commit())throw new IllegalStateException("Could not restore node cooldowns");
            radius=getSharedPreferences("survey-settings",0).getInt("radius",25);
            JSONObject setup=new JSONObject(PrivateStore.read(this));endpoint=setup.getString("url");token=setup.getString("token");nodePrefix=setup.getString("node_prefix").trim().toLowerCase(Locale.ROOT);if(!nodePrefix.matches("[a-z][a-z0-9]{0,7}"))throw new IllegalArgumentException("Invalid node prefix");
            BluetoothAdapter adapter=getSystemService(BluetoothManager.class).getAdapter();
            if(adapter==null||!adapter.isEnabled())throw new IllegalStateException("Turn Bluetooth on first");
            nonce=new java.security.SecureRandom().nextInt();if(nonce==0)nonce=1;
            if(SurveyRules.cadenceBlocked(getSharedPreferences("cadence",0).getLong("last_sent",0),epoch()))lastSent=clock();
            log("Connecting to the selected radio. Saved pairing loaded.");connectedAt=clock();ble=new MeshBle(this,adapter.getRemoteDevice(intent.getStringExtra("mac")),h,this);
            locations=getSystemService(LocationManager.class);
            if(checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION)==PackageManager.PERMISSION_GRANTED){
                Location cached=locations.getLastKnownLocation(LocationManager.GPS_PROVIDER);if(cached!=null)locationListener.onLocationChanged(cached);
                if(locations.isProviderEnabled(LocationManager.GPS_PROVIDER))locations.requestLocationUpdates(LocationManager.GPS_PROVIDER,10000,5,locationListener);
            }
            h.post(tick);
        }catch(Exception e){startupFailure="Could not start the connection. Check Bluetooth, app permissions and saved pairing, then reopen the app.";message=startupFailure;summary=message;log(message);stopSelf();}
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
    void pause(String reason){controlState.pause();armed=false;if(!reason.equals(message))log(reason);message=reason;notifyState();}
    void chooseChannel(int n){if(pending!=null){message="Wait for the outstanding traceroute before changing channel";return;}if(channels.containsKey(n)){channel=n;getSharedPreferences("survey-settings",0).edit().putInt("channel_"+own,n).apply();pause("Channel changed. Check the selected channel, then start the survey when ready.");}}
    void chooseRadius(int miles){radius=miles;getSharedPreferences("survey-settings",0).edit().putInt("radius",miles).apply();}
    String arm(){
        if(controlState.blocksRequests())return "Waiting for collector confirmation of the survey change.";
        if(!ready||!isLocal()||survey==0||clock()>=leaseUntil)return "Connect a local node and start a survey with a live collector connection.";
        if(position()==null)return "Waiting for a position within 24 hours and half-mile reported accuracy.";
        if(!channels.containsKey(channel))return "Choose an available radio channel first.";
        armed=true;message="Nearby nodes will be tried one at a time";log("Automatic survey enabled on slot "+channel+". Minimum interval: 30 seconds.");notifyState();return message;
    }
    public void written(byte[] raw){try{var sent=MeshProtos.ToRadio.parseFrom(raw);if(sent.hasPacket()&&sent.getPacket().getDecoded().getPortnum()==Portnums.PortNum.TRACEROUTE_APP)log("Bluetooth write completed for traceroute #"+unsigned(sent.getPacket().getId())+". RF reply not yet confirmed.");}catch(Exception ignored){}}
    public void ready(){log("Bluetooth connected. Reading radio configuration.");ble.send(MeshProtos.ToRadio.newBuilder().setWantConfigId(nonce).build().toByteArray());message="Reading node and channel configuration…";}
    public void failed(String reason){ready=false;pause(reason);if(pending!=null){result(pending,"transport_error",null);pending=null;}}
    public void received(byte[] raw){try{
        MeshProtos.FromRadio from=MeshProtos.FromRadio.parseFrom(raw);
        if(from.hasMyInfo()){
            int number=from.getMyInfo().getMyNodeNum();if(own!=0&&number!=own){ready=false;pause("Source radio changed. Stop and reconnect to verify it.");return;}if(own==0)channel=getSharedPreferences("survey-settings",0).getInt("channel_"+number,0);own=number;
            tried.clear();for(String saved:getSharedPreferences("cadence",0).getStringSet("tried_"+own+"_"+survey,Collections.emptySet()))tried.add(Integer.parseInt(saved));
        }
        if(from.hasNodeInfo())nodes.put(from.getNodeInfo().getNum(),from.getNodeInfo());
        if(from.hasChannel()){
            var c=from.getChannel();
            if(ready){pause("Channel configuration changed. Check the selected channel before resuming.");}
            if(c.getRoleValue()!=0){String n=c.getSettings().getName();channels.put(c.getIndex(),n.isEmpty()?"Unnamed "+c.getRole().name():n);}else channels.remove(c.getIndex());
        }
        if(from.getConfigCompleteId()==nonce){ready=SurveyRules.validId(unsigned(own))&&isLocal()&&!channels.isEmpty();message=ready?"Connected. Confirm the displayed local node and channel, then tap Start survey here.":"This radio is not identified as a local node, or its configuration is incomplete.";log(message);notifyState();}
        if(from.getRebooted()){ready=false;pause("Radio restarted. Stop and reconnect.");}
        if(from.hasPacket())packet(from.getPacket());
    }catch(Exception e){pause("Could not decode a radio message; reconnect before continuing.");ready=false;}}
    private void packet(MeshProtos.MeshPacket p)throws Exception {
        if(p.getViaMqtt())return; // Internet-delivered packets cannot verify an RF test.
        int n=p.getFrom();long now=epoch();
        // Passive metadata only: no message contents, keys or node database dumps.
        long rx=unsigned(p.getRxTime());
        if(receptionRecords&&survey>0&&ready&&clock()<leaseUntil&&n!=own&&SurveyRules.validId(unsigned(n))&&p.getId()!=0&&rx>0&&rx<=now&&now-rx<=120&&p.getRxRssi()>=-200&&p.getRxRssi()<0&&Float.isFinite(p.getRxSnr())&&Math.abs(p.getRxSnr())<=100&&p.getChannel()>=0&&p.getChannel()<=7&&outbox.count()<9900){
            JSONObject e=new JSONObject().put("id",UUID.randomUUID().toString()).put("kind","reception").put("survey_id",survey).put("source",unsigned(own)).put("time",now)
                .put("sender",unsigned(n)).put("packet_id",unsigned(p.getId())).put("channel",p.getChannel()).put("rx_time",rx).put("rssi",p.getRxRssi()).put("snr",p.getRxSnr()).put("via_mqtt",false);
            JSONObject loc=position();if(loc!=null)e.put("position",loc);
            if(!outbox.add(e))log("Could not save a passive reception; upload saved records.");
        }

        MeshProtos.NodeInfo.Builder node=nodes.containsKey(n)?nodes.get(n).toBuilder():MeshProtos.NodeInfo.newBuilder().setNum(n);
        node.setLastHeard((int)now).setViaMqtt(false);
        if(p.hasDecoded()){
            var data=p.getDecoded();
            if(data.getPortnum()==Portnums.PortNum.POSITION_APP)node.setPosition(MeshProtos.Position.parseFrom(data.getPayload()));
            if(data.getPortnum()==Portnums.PortNum.NODEINFO_APP)node.setUser(MeshProtos.User.parseFrom(data.getPayload()));
            nodes.put(n,node.build());
            Attempt a=attempts.get(data.getRequestId());
            if(a!=null&&p.getFrom()==a.dest&&p.getTo()==a.source&&p.getChannel()==a.channel&&data.getPortnum()==Portnums.PortNum.TRACEROUTE_APP){
                boolean late=a.done;
                MeshProtos.RouteDiscovery route=MeshProtos.RouteDiscovery.parseFrom(data.getPayload());
                JSONObject detail=new JSONObject().put("route",unsignedArray(route.getRouteList())).put("route_back",unsignedArray(route.getRouteBackList()))
                    .put("snr_towards_quarter_db",new JSONArray(route.getSnrTowardsList())).put("snr_back_quarter_db",new JSONArray(route.getSnrBackList()))
                    .put("response_packet_id",unsigned(p.getId())).put("response_from",unsigned(p.getFrom())).put("response_to",unsigned(p.getTo()));
                // Duplicate responses do not create more success records.
                if(!a.done||clock()-a.elapsed<=SurveyRules.TIMEOUT_MS+600000){
                    result(a,late?"late_success":"success",detail);attempts.remove(a.packet);
                    if(pending==a)pending=null;
                    if(a.test&&!late&&a.channel==channel&&a.source==own&&a.survey==survey)message="Manual test returned successfully.";
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
        if(phoneLocation!=null&&phoneLocation.hasAccuracy()&&SurveyRules.travellingAccuracyValid(phoneLocation.getAccuracy())&&SystemClock.elapsedRealtimeNanos()>=phoneLocation.getElapsedRealtimeNanos()&&SystemClock.elapsedRealtimeNanos()-phoneLocation.getElapsedRealtimeNanos()<=SurveyRules.POSITION_MAX_AGE_SECONDS*1_000_000_000L&&SurveyRules.travellingPositionFresh(phoneLocation.getTime()/1000,epoch())&&SurveyRules.validPosition(phoneLocation.getLatitude(),phoneLocation.getLongitude()))
            return new JSONObject().put("lat",phoneLocation.getLatitude()).put("lon",phoneLocation.getLongitude()).put("time",phoneLocation.getTime()/1000).put("source","phone_gps").put("accuracy_m",phoneLocation.getAccuracy());
        var node=nodes.get(own);if(node!=null&&node.hasPosition()){
            var p=node.getPosition();double lat=p.getLatitudeI()*1e-7,lon=p.getLongitudeI()*1e-7;
            if(p.getLocationSource()==MeshProtos.Position.LocSource.LOC_INTERNAL&&SurveyRules.validPosition(lat,lon)&&SurveyRules.travellingPositionFresh(positionTime(p),epoch()))return new JSONObject().put("lat",lat).put("lon",lon).put("time",positionTime(p)).put("source","radio_position");
        }
    }catch(Exception ignored){}return null;}
    private static long positionTime(MeshProtos.Position p){return unsigned(p.getTimestamp()!=0?p.getTimestamp():p.getTime());}
    List<Target> targets(){List<Target> result=new ArrayList<>();JSONObject loc=position();if(loc==null)return result;
        for(var n:nodes.values()){
            if(n.getViaMqtt()||n.getNum()==own||!SurveyRules.validId(unsigned(n.getNum()))||!n.hasPosition())continue;
            var p=n.getPosition();double lat=p.getLatitudeI()*1e-7,lon=p.getLongitudeI()*1e-7;
            if(p.getLocationSourceValue()<0||p.getLocationSourceValue()>3||p.getPrecisionBits()<0||p.getPrecisionBits()>32)continue;
            if(!SurveyRules.validPosition(lat,lon)||!SurveyRules.candidateFresh(positionTime(p),unsigned(n.getLastHeard()),epoch(),p.getLocationSourceValue()))continue;
            double miles=SurveyRules.miles(loc.optDouble("lat"),loc.optDouble("lon"),lat,lon);
            boolean automatic=SurveyRules.automaticCandidate(p.getLocationSourceValue(),p.getPrecisionBits());
            String source=p.getLocationSourceValue()==1?"fixed/manual (advertised)":p.getLocationSourceValue()==2?"radio GPS":p.getLocationSourceValue()==3?"external GPS":"unknown source";
            String precision=p.getPrecisionBits()==0?"precision unknown":p.getPrecisionBits()+"-bit advertised precision";
            if(miles<=radius)result.add(new Target(n.getNum(),miles,name(n.getNum())+" · "+id(n.getNum())+" · "+String.format(Locale.ROOT,"~%.1f mi · position %ds old · heard %ds ago",miles,Math.max(0,epoch()-positionTime(p)),Math.max(0,epoch()-unsigned(n.getLastHeard())))+" · "+source+" · "+precision+(automatic?"":" · manual test only"),automatic));
        }result.sort(Comparator.comparingDouble(t->t.distance));return result;
    }
    private String samplingKey(int dest){return "probe_"+dest;}
    private long sampledAt(int dest){return getSharedPreferences("cadence",0).getLong(samplingKey(dest)+"_time",0);}
    private boolean eligibleAgain(int dest){return SurveyRules.repeatEligible(sampledAt(dest),epoch());}
    String trace(int destination,boolean test){
        if(controlState.blocksRequests())return "Waiting for collector confirmation of the survey change.";
        if(!eligibleAgain(destination))return "This node was already tested within 8 hours. Wait before testing it again.";
        if(!SurveyRules.maySend(ready,isLocal(),pending!=null,clock(),lastSent,leaseUntil,survey)||!channels.containsKey(channel))return "Not ready: check the active survey, collector connection, channel, outstanding request and 30-second spacing.";

        if(targets().stream().noneMatch(t->t.number==destination&&(test||t.automatic)))return "This destination is no longer a nearby candidate with position data within the allowed age.";
        if(outbox.count()>=9990){pause("Upload the saved results before sending more requests");return message;}
        Attempt a=new Attempt();a.packet=new java.security.SecureRandom().nextInt();if(a.packet==0)a.packet=1;
        a.source=own;a.dest=destination;a.channel=channel;a.survey=survey;a.at=epoch();a.elapsed=clock();a.test=test;a.position=position();
        if(a.position==null)return "Location changed; wait for a position before testing.";
        try{var target=nodes.get(destination);var p=target.getPosition();a.destinationPosition=new JSONObject().put("lat",p.getLatitudeI()*1e-7).put("lon",p.getLongitudeI()*1e-7).put("time",positionTime(p)).put("last_heard",unsigned(target.getLastHeard())).put("source",p.getLocationSourceValue()).put("precision_bits",p.getPrecisionBits());}catch(Exception e){return "Destination position changed. Refresh the candidate list.";}
        MeshProtos.Data data=MeshProtos.Data.newBuilder().setPortnum(Portnums.PortNum.TRACEROUTE_APP).setPayload(ByteString.EMPTY).setWantResponse(true).build();
        MeshProtos.MeshPacket packet=MeshProtos.MeshPacket.newBuilder().setTo(destination).setId(a.packet).setChannel(channel).setHopLimit(3).setWantAck(true).setDecoded(data).build();
        try{
            // Save intent before submitting; a process restart never retries an uncertain send.
            if(!result(a,"requested",null))return "Could not save request intent; nothing was sent.";
            log("Saved request #"+unsigned(a.packet)+" to "+name(destination)+" on slot "+channel+"; submitting to Bluetooth.");
            a.done=false;attempts.put(a.packet,a);pending=a;lastSent=clock();tried.add(destination);
            Set<String> persisted=new HashSet<>();for(int n:tried)persisted.add(Integer.toString(n));
            if(!getSharedPreferences("cadence",0).edit().putLong(samplingKey(destination)+"_time",epoch()).putLong("last_sent",epoch()).putStringSet("tried_"+own+"_"+survey,persisted).commit()){
                result(a,"transport_error",null);pending=null;pause("Could not save request cadence; nothing was sent.");return message;
            }
            ble.send(MeshProtos.ToRadio.newBuilder().setPacket(packet).build().toByteArray());
            message="Requested traceroute to "+name(destination)+"; waiting up to 30 seconds. Late replies are still saved.";
        }catch(Exception e){result(a,"transport_error",null);pending=null;pause("Radio request could not be submitted; no automatic retry.");}
        return message;
    }
    private boolean result(Attempt a,String status,JSONObject details){try{
        JSONObject object=new JSONObject().put("id",UUID.randomUUID().toString()).put("kind","trace").put("survey_id",a.survey).put("source",unsigned(a.source)).put("destination",unsigned(a.dest))
            .put("packet_id",unsigned(a.packet)).put("channel",a.channel).put("requested_at",a.at).put("time",epoch()).put("status",status).put("test",a.test).put("position",a.position==null?JSONObject.NULL:a.position);
        if(details!=null)object.put("details",details);
        if(a.destinationPosition!=null)object.put("destination_position",a.destinationPosition);
        if(!outbox.add(object)){pause("Result storage is full; upload results before continuing.");return false;}
        if(!status.equals("requested")){a.done=true;message=name(a.dest)+": "+status.replace('_',' ');log("Request #"+unsigned(a.packet)+" · "+message);}
        return true;
    }catch(Exception e){pause("Could not save a survey result. Requests paused.");return false;}}
    private final Runnable tick=new Runnable(){public void run(){if(disposed)return;
        long now=clock();
        if(!ready&&connectedAt>0&&now-connectedAt>120000&&ble!=null){ble.close();connectedAt=0;pause("Radio configuration did not finish. Stop and reconnect.");}
        if(armed&&now>=leaseUntil)pause("Collector connection expired; requests paused. Re-enable after it reconnects.");
        if(pending!=null&&now-pending.elapsed>=SurveyRules.TIMEOUT_MS){result(pending,"timeout",null);pending=null;}
        if(ready&&now-lastHeartbeat>=60000){lastHeartbeat=now;try{ble.send(MeshProtos.ToRadio.newBuilder().setHeartbeat(MeshProtos.Heartbeat.newBuilder().setNonce(1)).build().toByteArray());}catch(Exception e){failed("Bluetooth heartbeat could not be sent");}}
        if(survey>0&&ready&&now<leaseUntil&&now-lastLocation>=15000){lastLocation=now;JSONObject loc=position();if(loc!=null)try{
            if(!outbox.add(new JSONObject().put("id",UUID.randomUUID().toString()).put("kind","position").put("survey_id",survey).put("source",unsigned(own)).put("time",epoch()).put("position",loc)))pause("Location storage is full. Upload saved results before continuing.");
            else log("Saved travelling position for survey #"+survey+"; awaiting collector acknowledgment.");
        }catch(Exception e){pause("Could not save survey location");}}
        if(!syncing&&!controlState.busy()&&now-lastSync>=15000){lastSync=now;sync();}
        if(armed&&pending==null&&now-lastSent>=SurveyRules.SPACING_MS){
            Target candidate=null;for(Target target:targets())if(target.automatic&&eligibleAgain(target.number)&&(candidate==null||sampledAt(target.number)<sampledAt(candidate.number)))candidate=target;
            if(candidate!=null){lastAutomaticWait="";trace(candidate.number,false);}
            else{String reason=position()==null?"Waiting for a travelling fix within 24 hours / 0.5-mile accuracy; no traceroute sent.":"Waiting for a fresh nearby candidate, an eligible node or the 8-hour repeat interval; no traceroute sent.";if(!reason.equals(lastAutomaticWait)){lastAutomaticWait=reason;message=reason;log(reason);}}
        }
        while(attempts.size()>32){Integer key=attempts.keySet().iterator().next();if(pending!=null&&key==pending.packet)break;attempts.remove(key);}
        summary=(ready?"Connected: ":"Radio: ")+name(own)+" "+(own==0?"":id(own))+"\nChannel "+channel+" · "+channels.getOrDefault(channel,"waiting for configuration")+
            "\n"+(survey>0?"Survey "+survey+" · "+area:"No active website survey")+"\nCollector: "+(now<leaseUntil?"connected":"offline / not yet paired")+
            "\nNearby: "+targets().size()+" within "+radius+" miles · tried "+tried.size()+"\n"+(armed?"Automatic requests enabled":"Automatic requests paused")+
            "\n"+(position()==null?"Waiting for a recent location":"Location available")+"\nSaved for upload: "+outbox.count()+"\n\n"+message;
        h.postDelayed(this,1000);
    }};
    private void sync(){syncing=true;final long syncStarted=clock();
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
                    outbox.acknowledge(reply.getJSONArray("accepted"),events);if(reply.getJSONArray("accepted").length()>0)log("Collector acknowledged "+reply.getJSONArray("accepted").length()+" saved records; "+outbox.count()+" remain queued.");else if(!collectorResponding)log("Collector connection verified. Saved pairing accepted.");long next=reply.optLong("survey_id",0);
                    if(next!=survey){survey=next;tried.clear();
                        for(String n:getSharedPreferences("cadence",0).getStringSet("tried_"+own+"_"+survey,Collections.emptySet()))tried.add(Integer.parseInt(n));
                        armed=false;message=next>0?"Survey ready. Check the channel and location, then start automatic requests.":"Website survey ended; no new requests.";notifyState();}
                    receptionRecords=reply.optBoolean("reception_records",false);collectorResponding=true;phoneControls=reply.optBoolean("phone_controls",false);area=reply.optString("area_name","");leaseUntil=syncStarted+Math.min(SurveyRules.LEASE_MS,Math.max(0,reply.optLong("lease_seconds",0))*1000);
                    if(controlState.synced(survey))message=arm();
                }catch(Exception e){controlState.failed();collectorResponding=false;leaseUntil=0;pause("Collector response was invalid");}finally{syncing=false;}});
            }catch(Exception e){h.post(()->{if(!disposed){syncing=false;controlState.failed();collectorResponding=false;leaseUntil=0;pause("Collector unavailable. Saved results retained; check your network connection and pairing.");}});}finally{if(connection!=null)connection.disconnect();connection=null;}});
        }catch(Exception e){syncing=false;leaseUntil=0;pause("Unable to prepare saved results for upload");}
    }
    boolean uiCanStartSession(){return phoneControls&&collectorResponding&&ready&&survey==0&&clock()<leaseUntil&&channels.containsKey(channel)&&position()!=null&&!controlState.blocksRequests()&&!syncing;}
    boolean uiCanEndSession(){return phoneControls&&collectorResponding&&survey>0&&!controlState.blocksRequests()&&!syncing;}
    void controlSurvey(boolean start){
        if(start?!uiCanStartSession():!uiCanEndSession()){message="Wait for a live collector connection, then try again.";return;}
        pause(start?"Starting roaming survey…":"Ending survey…");final long commandRevision=controlState.begin();
        try{
            JSONObject command=new JSONObject().put("id",UUID.randomUUID().toString()).put("action",start?"start":"stop").put("survey_id",survey);
            network.execute(()->{HttpURLConnection conn=null;try{
                conn=(HttpURLConnection)new URL(endpoint.substring(0,endpoint.length()-4)+"control").openConnection();connection=conn;
                conn.setInstanceFollowRedirects(false);conn.setConnectTimeout(10000);conn.setReadTimeout(12000);conn.setRequestMethod("POST");conn.setRequestProperty("Content-Type","application/json");conn.setRequestProperty("Authorization","Bearer "+token);conn.setDoOutput(true);
                byte[] body=command.toString().getBytes(StandardCharsets.UTF_8);conn.setFixedLengthStreamingMode(body.length);
                try(var output=conn.getOutputStream()){output.write(body);}
                if(conn.getResponseCode()!=200)throw new java.io.IOException("Collector did not confirm the action (HTTP "+conn.getResponseCode()+"). Refreshing survey status; pairing and saved results are retained.");
                byte[] bytes;try(var input=conn.getInputStream();var output=new java.io.ByteArrayOutputStream()){
                    byte[] buffer=new byte[4096];int count;while((count=input.read(buffer))!=-1){if(output.size()+count>65536)throw new java.io.IOException("Collector response too large");output.write(buffer,0,count);}bytes=output.toByteArray();
                }
                JSONObject reply=new JSONObject(new String(bytes,StandardCharsets.UTF_8));long confirmed=reply.getLong("survey_id");
                if(!reply.optBoolean("ok")||confirmed<=0||!(start?"start":"stop").equals(reply.optString("action")))throw new java.io.IOException("Collector response was invalid");
                h.post(()->{if(disposed)return;controlState.complete(commandRevision,start,confirmed);log(start?"Collector confirmed roaming survey #"+confirmed+" started.":"Collector confirmed survey #"+confirmed+" ended.");lastSync=0;message=start?"Survey started. Checking readiness…":"Survey ended. Saved results will continue uploading.";});
            }catch(Exception e){h.post(()->{if(disposed)return;controlState.failed();lastSync=0;message="Could not confirm survey change. Check Tailscale and collector status before trying again. No command was automatically retried.";log(message);});}finally{if(conn!=null)conn.disconnect();connection=null;}});
        }catch(Exception e){controlState.failed();message="Could not prepare survey action. Try again.";}
    }
    // Presentation-only state. These reads never send radio requests or change cadence.
    boolean uiPending(){return pending!=null;}
    boolean uiArmed(){return armed;}
    boolean uiCanPause(){return armed||controlState.blocksRequests();}
    boolean uiCanTest(){return !controlState.blocksRequests()&&SurveyRules.maySend(ready,isLocal(),pending!=null,clock(),lastSent,leaseUntil,survey)&&channels.containsKey(channel)&&position()!=null;}
    boolean uiCanArm(){return !controlState.blocksRequests()&&!armed&&channels.containsKey(channel)&&ready&&isLocal()&&survey>0&&clock()<leaseUntil&&position()!=null;}
    private String locationLabel(){JSONObject p=position();if(p==null)return "Waiting for a position within 24 hours / 0.5-mile accuracy";long age=Math.max(0,epoch()-p.optLong("time"));return ("phone_gps".equals(p.optString("source"))?"Phone GPS ±"+Math.round(p.optDouble("accuracy_m"))+" m":"Radio internal GPS · accuracy unknown")+" · "+(age>=60?(age/60)+" min old":age+"s old")+(age>300||p.optDouble("accuracy_m",0)>100?" · older / approximate fix":"");}
    String[] uiDetails(){
        long wait=Math.max(0,(SurveyRules.SPACING_MS-(clock()-lastSent)+999)/1000);
        String next=controlState.blocksRequests()?"Waiting for the collector to confirm survey status. New requests are paused.":!ready?"Next: wait for the radio configuration. If it stalls, disconnect and try again.":!collectorResponding?"Next: check your private network connection and collector pairing.":survey==0?(phoneControls?"Next: tap Start survey here when your location is ready.":"Collector update needed for Start survey on this phone."):position()==null?"Next: allow location access; a fix within 24 hours and half-mile accuracy is needed.":!channels.containsKey(channel)?"Next: choose an available radio channel.":pending!=null?"Waiting for a reply: "+Math.max(0,(SurveyRules.TIMEOUT_MS-(clock()-pending.elapsed)+999)/1000)+" seconds left. Late replies are still saved.":wait>0?"Next request available in "+wait+" seconds.":!armed?"Ready: start the automatic survey when you are ready.":"Survey running. Nearby nodes are tried one at a time.";
        return new String[]{"Radio · "+(own==0?"Connecting…":name(own)+" · "+id(own))+(ready?" · Connected":""),
            "Collector · "+(collectorResponding?"Connected":"Waiting for connection"),
            "Survey · "+(survey==0?"Not started":area+" · #"+survey),
            "Location · "+locationLabel()+" · "+targets().size()+" nearby candidates (estimated)",
            "Requests · "+(armed?"Automatic survey running":"Automatic requests paused")+(pending==null?"":" · Waiting for "+name(pending.dest)),
            outbox.count()+" records waiting to upload · "+tried.size()+" nodes tried",
            message,next,"Channel · slot "+channel+" · "+channels.getOrDefault(channel,"Waiting for configuration")};
    }
    public void onDestroy(){disposed=true;armed=false;ready=false;if(pending!=null)result(pending,"stopped",null);
        if(ble!=null)ble.close();if(locations!=null)try{locations.removeUpdates(locationListener);}catch(SecurityException ignored){}h.removeCallbacksAndMessages(null);if(connection!=null)connection.disconnect();network.shutdownNow();
        summary=(startupFailure.isEmpty()?"Stopped. Bluetooth released. ":startupFailure+" ")+outbox.count()+" saved records will upload when you reconnect.";log(summary);outbox.close();instance=null;stopForeground(STOP_FOREGROUND_REMOVE);super.onDestroy();
    }
}
