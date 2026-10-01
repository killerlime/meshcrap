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
    private LinearLayout pairingBox,connectionCard;
    private Button connectionToggle,primaryAction,startSessionButton,endSessionButton;
    private boolean connectionExpanded=true;
    private boolean savedPairing;
    private TextView logText;private ScrollView logScroll;private long logRevision=-1;
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
        nextStep=text("Let’s get ready for your outing.",18);nextStep.setTextColor(GREEN);
        card("Your outing");
        radioState=text("Radio · Not connected",18);collectorState=text("Collector · Waiting for a radio",16);
        surveyState=text("Survey · Start here when connected",16);locationState=text("Location · Waiting",16);
        activityState=text("Requests · Paused",16);queueState=text("",14);
        status=text(SurveyService.summary,14);status.setTextIsSelectable(true);
        primaryAction=button("Connect radio",()->{SurveyService s=SurveyService.instance;if(s==null){connectionExpanded=true;renderConnection();connectionCard.requestFocus();connectionCard.getParent().requestChildFocus(connectionCard,connectionCard);connect();}else if(s.uiCanStartSession()){s.controlSurvey(true);renderState();}else if(s.uiArmed()){s.pause("Paused by you");renderState();}else if(s.uiCanArm())enableSurvey();else if(s.uiCanTest())testTrace();});
        connectionToggle=button("Hide connection setup",()->{connectionExpanded=!connectionExpanded;renderConnection();});
        card("Connect your radio");connectionCard=body;
        text("Disconnect Meshtastic from this radio first. Meshcrap Survey needs its Bluetooth connection while you are out.",15);
        try{new JSONObject(PrivateStore.read(this)).getString("token");savedPairing=true;}catch(Exception ignored){}
        pairingState=text(savedPairing?"Collector pairing saved on this phone":"Pair this phone with your collector",16);
        pairingToggle=button(savedPairing?"Change collector pairing":"Enter pairing code",()->togglePairing());
        pairingBox=new LinearLayout(this);pairingBox.setOrientation(LinearLayout.VERTICAL);body.addView(pairingBox);
        TextView label=new TextView(this);label.setText("Pairing code from the dashboard’s Set up mobile app page");label.setTextColor(MUTED);label.setTextSize(14);pairingBox.addView(label);
        pairing=new EditText(this);pairing.setId(View.generateViewId());label.setLabelFor(pairing.getId());pairing.setHint("Paste pairing code here");pairing.setTextColor(INK);pairing.setHintTextColor(MUTED);pairing.setMinLines(2);pairing.setMaxLines(4);pairing.setInputType(android.text.InputType.TYPE_CLASS_TEXT|android.text.InputType.TYPE_TEXT_FLAG_MULTI_LINE|android.text.InputType.TYPE_TEXT_FLAG_NO_SUGGESTIONS);pairing.setSaveEnabled(false);pairing.setImportantForAutofill(View.IMPORTANT_FOR_AUTOFILL_NO);pairingBox.addView(pairing);
        pairingBox.setVisibility(savedPairing?View.GONE:View.VISIBLE);
        button("Save collector pairing",()->savePairing(()->message("Pairing saved securely on this phone. Connect your radio to verify collector access.")));
        button("Find my radio",()->permissions());
        button("Open Bluetooth settings",()->startActivity(new Intent(android.provider.Settings.ACTION_BLUETOOTH_SETTINGS)));
        devices=new Spinner(this);devices.setMinimumHeight(dp(52));devices.setContentDescription("Paired radio to use for this survey");body.addView(devices);
        deviceHint=text("",14);listRadios();
        connectButton=button("Connect radio",()->connect());
        card("Survey settings");
        startSessionButton=button("Start survey",()->{SurveyService s=SurveyService.instance;if(s!=null)s.controlSurvey(true);renderState();});
        endSessionButton=button("End survey",()->new AlertDialog.Builder(this).setTitle("End this survey?").setMessage("End the active survey on the collector and stop new requests. Saved results remain available; Bluetooth stays connected for uploads.").setPositiveButton("End survey",(d,n)->{SurveyService s=SurveyService.instance;if(s!=null)s.controlSurvey(false);renderState();}).setNegativeButton("Keep surveying",null).show());
        text("Start a roaming survey here: your route and results follow you across every grid. Slot 0 is used unless you choose another channel. Keep Tailscale or your private network connection active.",15);
        channelButton=button("Choose channel",()->chooseChannel());
        radiusButton=button("Nearby radius · 10 miles",()->chooseRadius());
        text("Nearby uses advertised positions, not proof of reachability. GPS candidates need a fix within 5 minutes; fixed/manual positions are labelled separately. Unknown source or coarse/missing precision allows manual tests only. Your travelling fix may be up to 1 hour old, with phone accuracy within half a mile. Age and accuracy remain visible.",14);
        card("Explore nearby nodes");
        text("Start the survey when the radio, channel, collector and location are ready. A manual test is optional.",15);
        testButton=button("Send an optional test traceroute",()->testTrace());
        autoButton=button("Start automatic survey",()->enableSurvey());
        pauseButton=button("Pause new requests",()->{if(SurveyService.instance!=null)SurveyService.instance.pause("Paused by you");renderState();});
        text("One request at a time, at least 30 seconds apart. Replies can take up to 30 seconds. Pausing lets the current request finish.",14);
        stopButton=button("Disconnect and release Bluetooth",()->new AlertDialog.Builder(this).setTitle("Disconnect radio?").setMessage("Stop this connection and release Bluetooth for Meshtastic. Any pending request ends; saved results stay on this phone.").setPositiveButton("Disconnect",(d,n)->stopService(new Intent(this,SurveyService.class))).setNegativeButton("Keep connected",null).show());
        card("Live activity");
        text("Evidence of what the app is doing. Bluetooth writes, radio replies and collector acknowledgments are separate steps. Latest 100 entries; kept in memory only.",14);
        logScroll=new ScrollView(this);logScroll.setFillViewport(true);body.addView(logScroll,new LinearLayout.LayoutParams(-1,dp(220)));
        logText=new TextView(this);logText.setTextColor(INK);logText.setTextSize(14);logText.setTextIsSelectable(true);logText.setPadding(dp(8),dp(8),dp(8),dp(8));logText.setContentDescription("Survey activity log");logScroll.addView(logText);
        button("Show latest activity",()->logScroll.fullScroll(View.FOCUS_DOWN));
        body=root;text("Results stay on this phone until the collector accepts them. GPS tracks show where you travelled; they do not prove radio coverage. Test build 0.4.3 · Bluetooth still needs verification on your phone.",13);
        button("Licenses and source",()->showLicenses());
        renderState();
    }
    private void showLicenses(){
        try{StringBuilder value=new StringBuilder();for(String file:new String[]{"NOTICE.txt","Protobuf-LICENSE.txt","GPL-3.0.txt"}){try(java.io.InputStream in=getAssets().open("licenses/"+file)){java.io.ByteArrayOutputStream out=new java.io.ByteArrayOutputStream();byte[] buffer=new byte[4096];int count;while((count=in.read(buffer))!=-1)out.write(buffer,0,count);value.append(new String(out.toByteArray(),java.nio.charset.StandardCharsets.UTF_8)).append("\n\n");}}
            ScrollView scroll=new ScrollView(this);TextView text=new TextView(this);text.setText(value.toString());text.setTextSize(14);text.setPadding(dp(16),dp(12),dp(16),dp(12));text.setTextIsSelectable(true);scroll.addView(text);new AlertDialog.Builder(this).setTitle("Licenses and source").setView(scroll).setPositiveButton("Close",null).show();
        }catch(java.io.IOException e){message("License files could not be opened. See the repository's Android LICENSE and third-party notices.");}
    }
    private int dp(int n){return Math.round(n*getResources().getDisplayMetrics().density);}
    private void card(String title){body=new LinearLayout(this);body.setOrientation(LinearLayout.VERTICAL);body.setPadding(dp(16),dp(12),dp(16),dp(16));android.graphics.drawable.GradientDrawable bg=new android.graphics.drawable.GradientDrawable();bg.setColor(0xff1a2820);bg.setCornerRadius(dp(16));bg.setStroke(dp(1),0xff344e3d);body.setBackground(bg);LinearLayout.LayoutParams lp=new LinearLayout.LayoutParams(-1,-2);lp.setMargins(0,dp(14),0,0);root.addView(body,lp);TextView heading=text(title,21);heading.setTextColor(GREEN);if(Build.VERSION.SDK_INT>=28)heading.setAccessibilityHeading(true);}
    private TextView text(String value,int size){TextView v=new TextView(this);v.setText(value);v.setTextSize(size);v.setTextColor(size>=16?INK:MUTED);v.setPadding(0,dp(6),0,dp(6));body.addView(v);return v;}
    private Button button(String label,Runnable r){Button b=new Button(this);b.setText(label);b.setAllCaps(false);b.setMinHeight(dp(52));b.setTextSize(16);b.setOnClickListener(v->r.run());LinearLayout.LayoutParams lp=new LinearLayout.LayoutParams(-1,-2);lp.setMargins(0,dp(5),0,0);body.addView(b,lp);return b;}
    private void togglePairing(){boolean show=pairingBox.getVisibility()!=View.VISIBLE;pairingBox.setVisibility(show?View.VISIBLE:View.GONE);if(show)pairing.requestFocus();else pairing.setText("");}
    private void renderConnection(){if(connectionCard==null)return;connectionCard.setVisibility(connectionExpanded?View.VISIBLE:View.GONE);connectionToggle.setText(connectionExpanded?"Hide connection setup":"Show connection setup");}
    private void renderState(){
        SurveyService s=SurveyService.instance;boolean active=s!=null;
        startSessionButton.setEnabled(active&&s.uiCanStartSession());endSessionButton.setEnabled(active&&s.uiCanEndSession());
        primaryAction.setText(!active?"Connect radio":s.uiCanStartSession()?"Start survey":s.uiArmed()?"Pause survey":s.uiCanArm()?"Start automatic survey":s.uiPending()?"Waiting for a reply…":s.uiCanTest()?"Choose a test node":"Getting ready…");
        primaryAction.setEnabled(!active||s.uiCanStartSession()||s.uiArmed()||s.uiCanArm()||s.uiCanTest());
        if(logRevision!=SurveyService.activityLog.revision()){
            boolean follow=logText.getHeight()<=logScroll.getHeight()+logScroll.getScrollY()+dp(24);
            logRevision=SurveyService.activityLog.revision();String entries=SurveyService.activityLog.snapshot();logText.setText(entries.isEmpty()?"Connect your radio to begin. No survey requests have been sent by this app session.":entries);
            if(follow)logScroll.post(()->logScroll.fullScroll(View.FOCUS_DOWN));
        }
        renderConnection();
        connectButton.setEnabled(!active);devices.setEnabled(!active);pairingToggle.setEnabled(!active);
        channelButton.setEnabled(active&&!s.uiPending());radiusButton.setEnabled(active);stopButton.setEnabled(active);
        testButton.setEnabled(active&&s.uiCanTest());autoButton.setEnabled(active&&s.uiCanArm());pauseButton.setEnabled(active&&s.uiCanPause());
        if(!active){radioState.setText("Radio · Not connected");collectorState.setText("Collector · "+(savedPairing?"Pairing saved; connect a radio":"Pairing needed"));surveyState.setText("Survey · Waiting for connection");locationState.setText("Location · Checked after connecting");activityState.setText("Requests · Stopped");queueState.setText("");status.setText(SurveyService.summary);nextStep.setText(savedPairing?"Next: select your paired local radio and tap Connect.":"Next: paste your collector pairing code, then choose a radio.");return;}
        String[] v=s.uiDetails();radioState.setText(v[0]);collectorState.setText(v[1]);surveyState.setText(v[2]);locationState.setText(v[3]);activityState.setText(v[4]);queueState.setText(v[5]);status.setText(v[6]);nextStep.setText(v[7]);channelButton.setText(v[8]);radiusButton.setText("Nearby radius · "+(int)s.radius+" miles");
    }
    private void chooseChannel(){SurveyService s=SurveyService.instance;if(s==null)return;List<Integer> ids=new ArrayList<>(s.channels.keySet());Collections.sort(ids);String[] labels=new String[ids.size()];for(int i=0;i<ids.size();i++)labels[i]="Slot "+ids.get(i)+" · "+s.channels.get(ids.get(i));if(ids.isEmpty()){message("Waiting for the radio’s channels. Try again when connected.");return;}new AlertDialog.Builder(this).setTitle("Survey channel").setItems(labels,(d,n)->{s.chooseChannel(ids.get(n));renderState();}).setNegativeButton("Cancel",null).show();}
    private void chooseRadius(){SurveyService s=SurveyService.instance;if(s==null)return;double[] miles={1,5,10,25};new AlertDialog.Builder(this).setTitle("Look for nodes within…").setItems(new String[]{"1 mile","5 miles","10 miles","25 miles"},(d,n)->{s.radius=miles[n];renderState();}).setNegativeButton("Cancel",null).show();}
    private void testTrace(){SurveyService s=SurveyService.instance;if(s==null)return;List<SurveyService.Target> targets=s.targets();if(targets.isEmpty()){message("No eligible nodes nearby. Check your location, try a wider radius, or wait for fresh node data.");return;}String[] labels=new String[targets.size()];for(int i=0;i<targets.size();i++)labels[i]=targets.get(i).label;new AlertDialog.Builder(this).setTitle("Send one test to…").setItems(labels,(d,n)->{message(s.trace(targets.get(n).number,true));renderState();}).setNegativeButton("Cancel",null).show();}
    private void enableSurvey(){SurveyService s=SurveyService.instance;if(s==null)return;new AlertDialog.Builder(this).setTitle("Start automatic survey?").setMessage("One request at a time, at least 30 seconds apart, with up to 30 seconds for a reply. Each eligible node is tried once per outing. Pause or disconnect at any time.").setPositiveButton("Start survey",(d,n)->{message(s.arm());renderState();}).setNegativeButton("Cancel",null).show();}
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
        devices.setAdapter(new ArrayAdapter<>(this,android.R.layout.simple_spinner_dropdown_item,labels));
        String last=getPreferences(0).getString("lastRadio","");for(int i=0;i<radios.size();i++)if(radios.get(i).getAddress().equals(last))devices.setSelection(i);deviceHint.setText(radios.isEmpty()?"No paired devices found. Pair your radio in Android settings, then tap Find paired radios.":"Select your local radio. Other paired Bluetooth devices may also appear.");
    }
    private void savePairing(Runnable afterSave){
        if(SurveyService.instance!=null){message("Disconnect the radio before changing collector pairing. Saved survey records will stay on this phone.");return;}
        String value=pairing.getText().toString().trim();
        if(value.isEmpty())try{value=PrivateStore.read(this);}catch(Exception e){message("The saved pairing could not be opened. Paste your existing collector code again. Saved survey records have not been removed.");return;}
        if(value.isEmpty()){message("Paste the full phone pairing code from the collector's setup page. The Bluetooth PIN and dashboard control key are different.");return;}
        final JSONObject setup;
        try{setup=new JSONObject(value);}catch(Exception e){message("The pasted text is not a complete phone pairing code. Copy the entire code, including its opening and closing braces.");return;}
        try{PairingRules.validateConnection(setup.optString("url",""),setup.optString("token",""));}
        catch(IllegalArgumentException e){message(e.getMessage());return;}
        if(!setup.has("node_prefix")){requestLegacyPrefix(setup,afterSave);return;}
        try{setup.put("node_prefix",PairingRules.validatePrefix(setup.optString("node_prefix","")));}
        catch(Exception e){message("The local radio-name prefix in this code is invalid. Check the collector's node-prefix setting. Your previous saved pairing is unchanged.");return;}
        persistPairing(setup,afterSave);
    }
    private void requestLegacyPrefix(JSONObject setup,Runnable afterSave){
        EditText prefix=new EditText(this);prefix.setSingleLine(true);prefix.setHint("Local radio-name prefix, for example MY");prefix.setContentDescription("Local radio-name prefix");prefix.setInputType(android.text.InputType.TYPE_CLASS_TEXT|android.text.InputType.TYPE_TEXT_FLAG_CAP_CHARACTERS);prefix.setSaveEnabled(false);
        AlertDialog dialog=new AlertDialog.Builder(this).setTitle("One detail for this older pairing code")
            .setMessage("This collector's code does not include your local radio-name prefix. Enter the common beginning of your radio names. This is not a password. Your existing code remains valid; no new pairing is needed.")
            .setView(prefix).setPositiveButton("Save pairing",null).setNegativeButton("Cancel",null).create();
        dialog.setOnShowListener(d->dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(v->{
            try{setup.put("node_prefix",PairingRules.validatePrefix(prefix.getText().toString()));}
            catch(Exception e){prefix.setError("Enter 1–8 letters or numbers, starting with a letter.");return;}
            dialog.dismiss();persistPairing(setup,afterSave);
        }));dialog.show();
    }
    private void persistPairing(JSONObject setup,Runnable afterSave){
        try{PrivateStore.save(this,setup.toString());}
        catch(Exception e){message("The pairing code is valid, but Android could not save it securely. Reopen the app and try again. Do not clear app data while survey results are waiting to upload.");return;}
        savedPairing=true;pairingState.setText("Collector pairing saved on this phone");pairingToggle.setText("Change collector pairing");pairing.setText("");pairingBox.setVisibility(View.GONE);
        afterSave.run();
    }
    private void connect(){
        if(SurveyService.instance!=null){message("Disconnect the current radio before connecting again.");return;}
        savePairing(this::connectSavedRadio);
    }
    @android.annotation.SuppressLint("MissingPermission") private void connectSavedRadio(){
        if(Build.VERSION.SDK_INT>=31&&!has(Manifest.permission.BLUETOOTH_CONNECT)){permissions();return;}
        if(radios.isEmpty()){message("Collector pairing is saved. Pair your radio in Android/Meshtastic, disconnect Meshtastic, then tap Find my radio here.");return;}
        int selected=devices.getSelectedItemPosition();if(selected<0||selected>=radios.size()){message("Collector pairing is saved. Select a paired radio first.");return;}
        try{
            String address=radios.get(selected).getAddress();Intent intent=new Intent(this,SurveyService.class).putExtra("mac",address);
            getPreferences(0).edit().putString("lastRadio",address).apply();startForegroundService(intent);connectionExpanded=false;renderConnection();
        }catch(Exception e){message("Collector pairing is saved, but the radio connection could not start. Check Bluetooth and app permissions, then try Connect radio again.");}
    }
    protected void onResume(){super.onResume();h.post(refresh);}
    protected void onPause(){h.removeCallbacks(refresh);super.onPause();}
}
