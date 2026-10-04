package org.meshcrap.survey;

import android.content.Context;
import android.content.ContentValues;
import android.database.Cursor;
import android.database.sqlite.SQLiteOpenHelper;
import android.database.sqlite.SQLiteDatabase;
import org.json.JSONArray;
import org.json.JSONObject;

final class Outbox extends SQLiteOpenHelper {
    static final int LIMIT=100000;
    private int cachedCount=-1;
    Outbox(Context c){super(c,"survey-outbox.db",null,1);}
    public void onCreate(SQLiteDatabase db){db.execSQL("CREATE TABLE outbox(id TEXT PRIMARY KEY,body TEXT NOT NULL)");}
    public void onUpgrade(SQLiteDatabase d,int a,int b){}
    synchronized boolean add(JSONObject object) {
        if(count()>=LIMIT)return false;
        ContentValues v=new ContentValues();v.put("id",object.optString("id"));v.put("body",object.toString());
        boolean added=getWritableDatabase().insertOrThrow("outbox",null,v)!=-1;
        if(added)cachedCount++;return added;
    }
    synchronized int count(){if(cachedCount>=0)return cachedCount;try(Cursor c=getReadableDatabase().rawQuery("SELECT count(*) FROM outbox",null)){c.moveToFirst();return cachedCount=c.getInt(0);}}
    synchronized JSONArray batch()throws Exception {
        JSONArray result=new JSONArray();try(Cursor c=getReadableDatabase().rawQuery("SELECT body FROM outbox ORDER BY rowid LIMIT 10",null)){
            while(c.moveToNext())result.put(new JSONObject(c.getString(0)));
        }return result;
    }
    synchronized void acknowledge(JSONArray ids,JSONArray submitted)throws Exception {
        java.util.Set<String> sent=new java.util.HashSet<>();java.util.List<String> accepted=new java.util.ArrayList<>();
        for(int i=0;i<submitted.length();i++)sent.add(submitted.getJSONObject(i).getString("id"));
        for(int i=0;i<ids.length();i++)accepted.add(ids.getString(i));
        SurveyRules.validateAcknowledgments(sent,accepted);
        SQLiteDatabase db=getWritableDatabase();db.beginTransaction();try{
        for(int i=0;i<ids.length();i++)db.delete("outbox","id=?",new String[]{ids.optString(i)});db.setTransactionSuccessful();
    }finally{db.endTransaction();cachedCount=-1;}}
}
