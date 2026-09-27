package org.jkmesh.survey;

import android.Manifest;
import android.app.*;
import android.bluetooth.*;
import android.content.*;
import android.content.pm.PackageManager;
import android.os.*;
import android.view.*;
import android.widget.*;
import java.util.*;
import org.json.JSONObject;

public final class MainActivity extends Activity {
    private final Handler h=new Handler(Looper.getMainLooper());
    private TextView status;private EditText pairing;private Spinner devices;
    private final ArrayList<BluetoothDevice> radios=new ArrayList<>();
    private final Runnable refresh=new Runnable(){public void run(){status.setText(SurveyService.summary);h.postDelayed(this,1000);}};
    private LinearLayout body;
    public void onCreate(Bundle saved){super.onCreate(saved);
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_SECURE);
        ScrollView scroll=new ScrollView(this);body=new LinearLayout(this);body.setOrientation(LinearLayout.VERTICAL);body.setPadding(24,36,24,48);scroll.addView(body);setContentView(scroll);
        text("Meshcrap Survey",26);text("Test build · private mesh coverage",16);
        text("Disconnect Meshtastic from the radio first. This app uses that Bluetooth connection during your outing. Stop here before reconnecting Meshtastic.",16);
        text("1 · Pair with your collector",20);
        pairing=new EditText(this);pairing.setHint("Paste the pairing code from the website’s Survey phone setup page. Leave blank to use saved pairing.");pairing.setMinLines(2);pairing.setMaxLines(4);pairing.setInputType(android.text.InputType.TYPE_CLASS_TEXT|android.text.InputType.TYPE_TEXT_FLAG_MULTI_LINE|android.text.InputType.TYPE_TEXT_FLAG_NO_SUGGESTIONS);body.addView(pairing);
        button("Allow Bluetooth / location and list paired radios",()->permissions());
        devices=new Spinner(this);devices.setContentDescription("Paired radio to use for this survey");body.addView(devices);listRadios();
        button("Connect selected radio",()->connect());
        text("2 · Start a survey on the website",20);
        text("Choose either coverage area, then Start Coverage Survey. The phone will show the active survey and connected node. Radio GPS or an accurate phone location is needed to find nearby nodes.",16);
        status=text(SurveyService.summary,16);status.setTextIsSelectable(true);
        button("Choose channel",()->{SurveyService s=SurveyService.instance;if(s==null){message("Connect a radio first");return;}
            List<Integer> ids=new ArrayList<>(s.channels.keySet());Collections.sort(ids);String[] labels=new String[ids.size()];for(int i=0;i<ids.size();i++)labels[i]=ids.get(i)+" · "+s.channels.get(ids.get(i));
            if(ids.isEmpty()){message("Waiting for the radio’s channel configuration");return;}
            new AlertDialog.Builder(this).setTitle("Survey channel").setItems(labels,(d,n)->s.chooseChannel(ids.get(n))).show();});
        button("Nearby radius",()->{SurveyService s=SurveyService.instance;if(s==null){message("Connect first");return;}double[] miles={1,5,10,25};new AlertDialog.Builder(this).setTitle("Nearby radius").setItems(new String[]{"1 mile","5 miles","10 miles","25 miles"},(d,n)->s.radius=miles[n]).show();});
        button("Send one test traceroute…",()->{
            SurveyService s=SurveyService.instance;if(s==null){message("Connect first");return;}
            List<SurveyService.Target> targets=s.targets();if(targets.isEmpty()){message("No recently heard nodes with recent positions inside the chosen radius. Check your location and radio node list.");return;}
            String[] labels=new String[targets.size()];for(int i=0;i<targets.size();i++)labels[i]=targets.get(i).label;
            new AlertDialog.Builder(this).setTitle("Choose the one test destination").setItems(labels,(d,n)->message(s.trace(targets.get(n).number,true))).setNegativeButton("Cancel",null).show();
        });
        button("Enable nearby-node survey",()->{
            SurveyService s=SurveyService.instance;if(s==null){message("Connect first");return;}
            new AlertDialog.Builder(this).setTitle("Enable paced traceroutes?").setMessage("One request at a time, at least two minutes apart, up to five minutes for a response. Each nearby candidate is tried once per survey. A successful test on this connection and channel is required first.")
                .setPositiveButton("Enable",(d,n)->message(s.arm())).setNegativeButton("Cancel",null).show();
        });
        button("Pause requests",()->{if(SurveyService.instance!=null)SurveyService.instance.pause("Paused by you");});
        button("Stop and release Bluetooth",()->stopService(new Intent(this,SurveyService.class)));
        text("Results are saved on this phone until the collector acknowledges them. GPS positions describe your path; they do not, by themselves, prove radio coverage. No channel keys or private admin keys are sent to the collector.",14);
    }
    private TextView text(String value,int size){TextView v=new TextView(this);v.setText(value);v.setTextSize(size);v.setPadding(0,12,0,12);body.addView(v);return v;}
    private void button(String label,Runnable r){Button b=new Button(this);b.setText(label);b.setAllCaps(false);b.setOnClickListener(v->r.run());body.addView(b);}
    private void message(String value){new AlertDialog.Builder(this).setMessage(value).setPositiveButton("OK",null).show();}
    private boolean has(String permission){return checkSelfPermission(permission)==PackageManager.PERMISSION_GRANTED;}
    private void permissions(){ArrayList<String> p=new ArrayList<>();
        if(Build.VERSION.SDK_INT>=31&&!has(Manifest.permission.BLUETOOTH_CONNECT))p.add(Manifest.permission.BLUETOOTH_CONNECT);
        if(!has(Manifest.permission.ACCESS_FINE_LOCATION)){p.add(Manifest.permission.ACCESS_FINE_LOCATION);p.add(Manifest.permission.ACCESS_COARSE_LOCATION);}
        if(Build.VERSION.SDK_INT>=33&&!has(Manifest.permission.POST_NOTIFICATIONS))p.add(Manifest.permission.POST_NOTIFICATIONS);
        if(p.isEmpty())listRadios();else requestPermissions(p.toArray(new String[0]),1);
    }
    @Override public void onRequestPermissionsResult(int n,String[] p,int[] result){super.onRequestPermissionsResult(n,p,result);listRadios();}
    @android.annotation.SuppressLint("MissingPermission") private void listRadios(){
        if(Build.VERSION.SDK_INT>=31&&!has(Manifest.permission.BLUETOOTH_CONNECT))return;
        BluetoothManager manager=getSystemService(BluetoothManager.class);BluetoothAdapter adapter=manager==null?null:manager.getAdapter();if(adapter==null)return;
        radios.clear();radios.addAll(adapter.getBondedDevices());radios.sort(Comparator.comparing(d->String.valueOf(d.getName())));
        List<String> labels=new ArrayList<>();for(BluetoothDevice d:radios)labels.add((d.getName()==null?"Paired device":d.getName())+" · "+d.getAddress());
        devices.setAdapter(new ArrayAdapter<>(this,android.R.layout.simple_spinner_dropdown_item,labels));
    }
    @android.annotation.SuppressLint("MissingPermission") private void connect(){
        if(Build.VERSION.SDK_INT>=31&&!has(Manifest.permission.BLUETOOTH_CONNECT)){permissions();return;}
        if(radios.isEmpty()){message("Pair your radio in Android/Meshtastic first, then disconnect Meshtastic and list radios again.");return;}
        if(SurveyService.instance!=null){message("Stop the current connection before selecting another radio.");return;}
        try{
            String value=pairing.getText().toString().trim();if(value.isEmpty())value=PrivateStore.read(this);
            JSONObject setup=new JSONObject(value);java.net.URI uri=new java.net.URI(setup.getString("url"));
            if(!"https".equals(uri.getScheme())||uri.getHost()==null||uri.getHost().isEmpty()||uri.getUserInfo()!=null||uri.getPort()!=-1||!"/api/survey-phone/sync".equals(uri.getPath())||uri.getQuery()!=null||uri.getFragment()!=null||setup.getString("token").length()<32||!setup.getString("node_prefix").matches("[A-Za-z][A-Za-z0-9]{0,7}"))throw new IllegalArgumentException();
            PrivateStore.save(this,value);pairing.setText("");
            Intent intent=new Intent(this,SurveyService.class).putExtra("mac",radios.get(devices.getSelectedItemPosition()).getAddress());
            startForegroundService(intent);
        }catch(Exception e){message("Paste a valid pairing code from the collector’s private HTTPS setup page. Pairing could not be saved or opened.");}
    }
    protected void onResume(){super.onResume();h.post(refresh);}
    protected void onPause(){h.removeCallbacks(refresh);super.onPause();}
}
