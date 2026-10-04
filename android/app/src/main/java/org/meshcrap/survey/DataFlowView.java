package org.meshcrap.survey;

import android.animation.ValueAnimator;
import android.content.Context;
import android.graphics.*;
import android.os.SystemClock;
import android.view.View;

/** Presentation only: pulses describe observed transfers, never initiate them. */
final class DataFlowView extends View {
    private final Paint paint=new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Rect visible=new Rect();
    private final RectF box=new RectF();
    private boolean foreground=false,motion=true,radio=false,online=false,uploading=false,stacked=false;
    private long received=0,sent=0,accepted=0;
    private int queued=0;
    private static final int GREEN=0xff79e5a0,BLUE=0xff80d7ff,AMBER=0xffffcf70,MUTED=0xff829c8c;
    DataFlowView(Context c){super(c);setImportantForAccessibility(IMPORTANT_FOR_ACCESSIBILITY_YES);setFocusable(true);}
    void foreground(boolean value){foreground=value;if(value)invalidate();}
    void motion(boolean value){motion=value;invalidate();}
    void update(boolean radio,boolean online,boolean uploading,int queued,long received,long sent,long accepted){
        this.radio=radio;this.online=online;this.uploading=uploading;this.queued=queued;
        this.received=received;this.sent=sent;this.accepted=accepted;
        String description="Data flow. Radio "+(radio?"connected":"disconnected")+". Phone: "+(queued<0?"connect to see saved records":queued+" records waiting")+". Collector "+(online?"connected": "offline; data stays on phone")+(uploading?". Upload in progress":"")+". Blue arrows are completed Bluetooth request writes, not confirmed RF delivery. Green arrows show packets received or collector-acknowledged uploads.";
        if(!description.contentEquals(getContentDescription()==null?"":getContentDescription()))setContentDescription(description);
        invalidate();
    }
    private float dp(float n){return n*getResources().getDisplayMetrics().density;}
    private float sp(float n){return n*getResources().getDisplayMetrics().scaledDensity;}
    private boolean vertical(){return stacked;}
    @Override protected void onMeasure(int w,int h){stacked=getResources().getConfiguration().fontScale>1.3f||MeasureSpec.getSize(w)<dp(260);setMeasuredDimension(MeasureSpec.getSize(w),Math.round(dp(vertical()?320:172)));}
    private static boolean recent(long stamp,long now){return stamp>0&&now>=stamp&&now-stamp<4000;}
    private void label(Canvas c,String text,float x,float y,int color,float size){paint.setColor(color);paint.setStyle(Paint.Style.FILL);paint.setTextAlign(Paint.Align.CENTER);paint.setTextSize(sp(size));c.drawText(text,x,y,paint);}
    private void node(Canvas c,float x,float y,String name,String state,int color,boolean phone){
        float half=dp(vertical()?64:37),height=dp(32);
        box.set(x-half,y-height,x+half,y+height);paint.setColor(0xff101b15);paint.setStyle(Paint.Style.FILL);c.drawRoundRect(box,dp(10),dp(10),paint);
        if(phone&&queued>0){paint.setColor(0xff4c452b);float fill=(float)Math.min(1,Math.log10(queued+1)/5);c.drawRect(x-half+dp(4),y+height-dp(5)-dp(16)*fill,x+half-dp(4),y+height-dp(5),paint);}
        paint.setStyle(Paint.Style.STROKE);paint.setStrokeWidth(dp(1.5f));paint.setColor(color);c.drawRoundRect(box,dp(10),dp(10),paint);
        label(c,name,x,y-dp(5),0xffe8f1eb,12);label(c,state,x,y+dp(16),color,vertical()?10:10);
    }
    private void lane(Canvas c,float x1,float y1,float x2,float y2,int color,long stamp,long now,boolean animate){
        boolean active=recent(stamp,now);paint.setStyle(Paint.Style.STROKE);paint.setStrokeWidth(dp(2));paint.setColor(active?color:0xff405749);c.drawLine(x1,y1,x2,y2,paint);
        float dx=x2-x1,dy=y2-y1,length=(float)Math.hypot(dx,dy);if(length<1)return;
        float ux=dx/length,uy=dy/length,tip=dp(5);
        c.drawLine(x2,y2,x2-tip*ux+tip*.65f*uy,y2-tip*uy-tip*.65f*ux,paint);
        c.drawLine(x2,y2,x2-tip*ux-tip*.65f*uy,y2-tip*uy+tip*.65f*ux,paint);
        if(active){paint.setStyle(Paint.Style.FILL);paint.setColor(color);
            for(int i=0;i<2;i++){float t=animate?((now-stamp)%1200)/1200f+i*.5f:.35f+i*.3f;t%=1;c.drawCircle(x1+dx*t,y1+dy*t,dp(3.2f),paint);}}
    }
    @Override protected void onDraw(Canvas c){super.onDraw(c);long now=SystemClock.elapsedRealtime();
        boolean animate=foreground&&motion&&ValueAnimator.areAnimatorsEnabled()&&isShown()&&getGlobalVisibleRect(visible);
        float w=getWidth(),x1=dp(38),x2=w/2,x3=w-dp(38),y=dp(70);
        if(vertical()){
            float x=w/2,a=dp(38),b=dp(144),d=dp(250);
            lane(c,x-dp(10),a+dp(34),x-dp(10),b-dp(34),GREEN,radio?received:0,now,animate);
            lane(c,x+dp(10),b-dp(34),x+dp(10),a+dp(34),BLUE,radio?sent:0,now,animate);
            lane(c,x,b+dp(34),x,d-dp(34),GREEN,online?accepted:0,now,animate);
            node(c,x,a,"Radio",radio?"Connected":"Waiting",radio?GREEN:MUTED,false);
            node(c,x,b,"Phone",queued<0?"Saved data":queued+" queued",queued>0?AMBER:GREEN,true);
            node(c,x,d,"Collector",uploading?"Sending…":online?"Connected":"Offline",online?GREEN:AMBER,false);
        }else{
            lane(c,x1+dp(38),y-dp(9),x2-dp(38),y-dp(9),GREEN,radio?received:0,now,animate);
            lane(c,x2-dp(38),y+dp(9),x1+dp(38),y+dp(9),BLUE,radio?sent:0,now,animate);
            lane(c,x2+dp(38),y,x3-dp(38),y,GREEN,online?accepted:0,now,animate);
            node(c,x1,y,"Radio",radio?"Connected":"Waiting",radio?GREEN:MUTED,false);
            node(c,x2,y,"Phone",queued<0?"Saved data":queued+" queued",queued>0?AMBER:GREEN,true);
            node(c,x3,y,"Collector",uploading?"Sending…":online?"Connected":"Offline",online?GREEN:AMBER,false);
            label(c,uploading?"Uploading saved records…":!online?"Offline · records stay on this phone":queued>0?"Saved records waiting to upload":"Caught up · waiting for activity",w/2,dp(132),queued>0?AMBER:MUTED,12);
        }
        if(animate&&(recent(received,now)||recent(sent,now)||recent(accepted,now)))postInvalidateDelayed(40);
    }
}
