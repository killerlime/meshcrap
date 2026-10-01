package org.meshcrap.survey;

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
    private TextView nextStep,radioState,collectorState,surveyState,locationState,activityState,queueState,pairingState,deviceHint;
    private Button connectButton,channelButton,radiusButton,testButton,autoButton,pauseButton,stopButton,pairingToggle;
    private LinearLayout pairingBox;
    private boolean savedPairing;
    private final Runnable refresh=new Runnable(){public void run(){renderState();h.postDelayed(this,1000);}};
    private LinearLayout body,root;
    private static final int GREEN=0xff79e5a0,INK=0xffe8f1eb,MUTED=0xffb2c8b9;
    public void onCreate(Bundle saved){super.onCreate(saved);
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_SECURE);
        getWindow().setStatusBarColor(0xff101813);getWindow().setNavigationBarColor(0xff101813);
        ScrollView scroll=new ScrollView(this);scroll.setFillViewport(true);scroll.setBackgroundColor(0xff101813);
        root=new LinearLayout(this);root.setOrientation(LinearLayout.VERTICAL);root.setPadding(dp(18),dp(20),dp(18),dp(28));body=root;scroll.addView(root);setContentView(scroll);
        root.setOnApplyWindowInsetsListener((v,insets)->{root.setPadding(dp(18)+insets.getSystemWindowInsetLeft(),dp(20)+insets.getSystemWindowInsetTop(),dp(18)+insets.getSystemWindowInsetRight(),dp(28)+insets.getSystemWindowInsetBottom());return insets;});
        text("Meshcrap Survey",30).setTextColor(GREEN);text("A field companion for your mesh",16);
        nextStep=text("First, connect your radio below.",18);nextStep.setTextColor(GREEN);
        card("Your outing");
        radioState=text("Radio · Not connected",18);collectorState=text("Collector · Waiting for a radio",16);
        surveyState=text("Survey · Start one on the dashboard",16);locationState=text("Location · Waiting",16);
        activityState=text("Requests · Paused",16);queueState=text("",14);
        status=text(SurveyService.summary,14);status.setTextIsSelectable(true);
        card("1  Connect your radio");
        text("Disconnect Meshtastic from this radio first. Meshcrap Survey needs its Bluetooth connection while you are out.",15);
        try{new JSONObject(PrivateStore.read(this)).getString("token");savedPairing=true;}catch(Exception ignored){}
        pairingState=text(savedPairing?"Collector pairing saved on this phone":"Pair this phone with your collector",16);
        pairingToggle=button(savedPairing?"Change collector pairing":"Enter pairing code",()->togglePairing());
        pairingBox=new LinearLayout(this);pairingBox.setOrientation(LinearLayout.VERTICAL);body.addView(pairingBox);
        TextView label=new TextView(this);label.setText("Pairing code from the dashboard’s Set up mobile app page");label.setTextColor(MUTED);label.setTextSize(14);pairingBox.addView(label);
        pairing=new EditText(this);pairing.setId(View.generateViewId());label.setLabelFor(pairing.getId());pairing.setHint("Paste pairing code here");pairing.setTextColor(INK);pairing.setHintTextColor(MUTED);pairing.setMinLines(2);pairing.setMaxLines(4);pairing.setInputType(android.text.InputType.TYPE_CLASS_TEXT|android.text.InputType.TYPE_TEXT_FLAG_MULTI_LINE|android.text.InputType.TYPE_TEXT_FLAG_NO_SUGGESTIONS);pairing.setSaveEnabled(false);pairing.setImportantForAutofill(View.IMPORTANT_FOR_AUTOFILL_NO);pairingBox.addView(pairing);
        pairingBox.setVisibility(savedPairing?View.GONE:View.VISIBLE);
        button("Find paired radios / allow permissions",()->permissions());
        devices=new Spinner(this);devices.setMinimumHeight(dp(52));devices.setContentDescription("Paired radio to use for this survey");body.addView(devices);
        deviceHint=text("",14);listRadios();
        connectButton=button("Connect radio",()->connect());
        card("2  Check your survey");
        text("On the dashboard, choose a coverage area and start a coverage survey. Keep Tailscale connected on this phone.",15);
        channelButton=button("Choose channel",()->chooseChannel());
        radiusButton=button("Nearby radius · 10 miles",()->chooseRadius());
        text("Nearby nodes need recent reception and a known position. A recent radio position or accurate phone GPS is needed too.",14);
        card("3  Test, then explore");
        text("Send one test first. After a successful reply, you can enable automatic requests to nearby nodes.",15);
        testButton=button("Send one test traceroute",()->testTrace());
        autoButton=button("Start automatic survey",()->enableSurvey());
        pauseButton=button("Pause new requests",()->{if(SurveyService.instance!=null)SurveyService.instance.pause("Paused by you");renderState();});
        text("One request at a time, at least 2 minutes apart. Replies can take up to 5 minutes. Pausing lets the current request finish.",14);
        stopButton=button("Disconnect and release Bluetooth",()->new AlertDialog.Builder(this).setTitle("Disconnect radio?").setMessage("Stop this connection and release Bluetooth for Meshtastic. Any pending request ends; saved results stay on this phone.").setPositiveButton("Disconnect",(d,n)->stopService(new Intent(this,SurveyService.class))).setNegativeButton("Keep connected",null).show());
        body=root;text("Results stay on this phone until the collector accepts them. GPS tracks show where you travelled; they do not prove radio coverage. Test build 0.2 · Bluetooth still needs verification on your phone.",13);
        renderState();
    }
    private int dp(int n){return Math.round(n*getResources().getDisplayMetrics().density);}
    private void card(String title){body=new LinearLayout(this);body.setOrientation(LinearLayout.VERTICAL);body.setPadding(dp(16),dp(12),dp(16),dp(16));android.graphics.drawable.GradientDrawable bg=new android.graphics.drawable.GradientDrawable();bg.setColor(0xff1a2820);bg.setCornerRadius(dp(16));bg.setStroke(dp(1),0xff344e3d);body.setBackground(bg);LinearLayout.LayoutParams lp=new LinearLayout.LayoutParams(-1,-2);lp.setMargins(0,dp(14),0,0);root.addView(body,lp);TextView heading=text(title,21);heading.setTextColor(GREEN);if(Build.VERSION.SDK_INT>=28)heading.setAccessibilityHeading(true);}
    private TextView text(String value,int size){TextView v=new TextView(this);v.setText(value);v.setTextSize(size);v.setTextColor(size>=16?INK:MUTED);v.setPadding(0,dp(6),0,dp(6));body.addView(v);return v;}
    private Button button(String label,Runnable r){Button b=new Button(this);b.setText(label);b.setAllCaps(false);b.setMinHeight(dp(52));b.setTextSize(16);b.setOnClickListener(v->r.run());LinearLayout.LayoutParams lp=new LinearLayout.LayoutParams(-1,-2);lp.setMargins(0,dp(5),0,0);body.addView(b,lp);return b;}
    private void togglePairing(){boolean show=pairingBox.getVisibility()!=View.VISIBLE;pairingBox.setVisibility(show?View.VISIBLE:View.GONE);if(show)pairing.requestFocus();else pairing.setText("");}
    private void renderState(){
        SurveyService s=SurveyService.instance;boolean active=s!=null;
        connectButton.setEnabled(!active);devices.setEnabled(!active);pairingToggle.setEnabled(!active);
        channelButton.setEnabled(active&&!s.uiPending());radiusButton.setEnabled(active);stopButton.setEnabled(active);
        testButton.setEnabled(active&&s.uiCanTest());autoButton.setEnabled(active&&s.uiCanArm());pauseButton.setEnabled(active&&s.uiArmed());
        if(!active){radioState.setText("Radio · Not connected");collectorState.setText("Collector · "+(savedPairing?"Pairing saved; connect a radio":"Pairing needed"));surveyState.setText("Survey · Waiting for connection");locationState.setText("Location · Checked after connecting");activityState.setText("Requests · Stopped");queueState.setText("");status.setText(SurveyService.summary);nextStep.setText(savedPairing?"Next: select your paired local radio and tap Connect.":"Next: paste your collector pairing code, then choose a radio.");return;}
        String[] v=s.uiDetails();radioState.setText(v[0]);collectorState.setText(v[1]);surveyState.setText(v[2]);locationState.setText(v[3]);activityState.setText(v[4]);queueState.setText(v[5]);status.setText(v[6]);nextStep.setText(v[7]);channelButton.setText(v[8]);radiusButton.setText("Nearby radius · "+(int)s.radius+" miles");
    }
    private void chooseChannel(){SurveyService s=SurveyService.instance;if(s==null)return;List<Integer> ids=new ArrayList<>(s.channels.keySet());Collections.sort(ids);String[] labels=new String[ids.size()];for(int i=0;i<ids.size();i++)labels[i]="Slot "+ids.get(i)+" · "+s.channels.get(ids.get(i));if(ids.isEmpty()){message("Waiting for the radio’s channels. Try again when connected.");return;}new AlertDialog.Builder(this).setTitle("Survey channel").setItems(labels,(d,n)->{s.chooseChannel(ids.get(n));renderState();}).setNegativeButton("Cancel",null).show();}
    private void chooseRadius(){SurveyService s=SurveyService.instance;if(s==null)return;double[] miles={1,5,10,25};new AlertDialog.Builder(this).setTitle("Look for nodes within…").setItems(new String[]{"1 mile","5 miles","10 miles","25 miles"},(d,n)->{s.radius=miles[n];renderState();}).setNegativeButton("Cancel",null).show();}
    private void testTrace(){SurveyService s=SurveyService.instance;if(s==null)return;List<SurveyService.Target> targets=s.targets();if(targets.isEmpty()){message("No eligible nodes nearby. Check your location, try a wider radius, or wait for fresh node data.");return;}String[] labels=new String[targets.size()];for(int i=0;i<targets.size();i++)labels[i]=targets.get(i).label;new AlertDialog.Builder(this).setTitle("Send one test to…").setItems(labels,(d,n)->{message(s.trace(targets.get(n).number,true));renderState();}).setNegativeButton("Cancel",null).show();}
    private void enableSurvey(){SurveyService s=SurveyService.instance;if(s==null)return;new AlertDialog.Builder(this).setTitle("Start automatic survey?").setMessage("One request at a time, at least 2 minutes apart, with up to 5 minutes for a reply. Each eligible node is tried once per outing. Pause or disconnect at any time.").setPositiveButton("Start survey",(d,n)->{message(s.arm());renderState();}).setNegativeButton("Cancel",null).show();}
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
        if(Build.VERSION.SDK_INT>=31&&!has(Manifest.permission.BLUETOOTH_CONNECT)){deviceHint.setText("Allow Bluetooth access above to list your paired radios.");return;}
        BluetoothManager manager=getSystemService(BluetoothManager.class);BluetoothAdapter adapter=manager==null?null:manager.getAdapter();if(adapter==null){deviceHint.setText("Bluetooth is unavailable on this device.");return;}if(!adapter.isEnabled()){deviceHint.setText("Turn on Bluetooth in Android settings, then tap Find paired radios.");return;}
        radios.clear();radios.addAll(adapter.getBondedDevices());radios.sort(Comparator.comparing(d->String.valueOf(d.getName())));
        List<String> labels=new ArrayList<>();for(BluetoothDevice d:radios)labels.add((d.getName()==null?"Paired device":d.getName())+" · "+d.getAddress());
        devices.setAdapter(new ArrayAdapter<>(this,android.R.layout.simple_spinner_dropdown_item,labels));deviceHint.setText(radios.isEmpty()?"No paired devices found. Pair your radio in Android settings, then tap Find paired radios.":"Select your local radio. Other paired Bluetooth devices may also appear.");
    }
    @android.annotation.SuppressLint("MissingPermission") private void connect(){
        if(Build.VERSION.SDK_INT>=31&&!has(Manifest.permission.BLUETOOTH_CONNECT)){permissions();return;}
        if(radios.isEmpty()){message("Pair your radio in Android/Meshtastic first, then disconnect Meshtastic and list radios again.");return;}
        if(SurveyService.instance!=null){message("Stop the current connection before selecting another radio.");return;}
        try{
            String value=pairing.getText().toString().trim();if(value.isEmpty())value=PrivateStore.read(this);
            JSONObject setup=new JSONObject(value);java.net.URI uri=new java.net.URI(setup.getString("url"));
            if(!"https".equals(uri.getScheme())||uri.getHost()==null||uri.getUserInfo()!=null||uri.getPort()!=-1||!"/api/survey-phone/sync".equals(uri.getPath())||uri.getQuery()!=null||uri.getFragment()!=null||setup.getString("token").length()<32||!setup.getString("node_prefix").matches("[A-Za-z][A-Za-z0-9]{0,7}"))throw new IllegalArgumentException();
            PrivateStore.save(this,value);savedPairing=true;pairingState.setText("Collector pairing saved on this phone");pairingToggle.setText("Change collector pairing");pairing.setText("");pairingBox.setVisibility(View.GONE);
            Intent intent=new Intent(this,SurveyService.class).putExtra("mac",radios.get(devices.getSelectedItemPosition()).getAddress());
            startForegroundService(intent);
        }catch(Exception e){message("Paste a valid pairing code from the collector’s private HTTPS setup page. Pairing could not be saved or opened.");}
    }
    protected void onResume(){super.onResume();h.post(refresh);}
    protected void onPause(){h.removeCallbacks(refresh);super.onPause();}
}
