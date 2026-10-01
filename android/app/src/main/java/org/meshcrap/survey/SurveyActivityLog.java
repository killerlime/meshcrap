package org.meshcrap.survey;

import java.text.SimpleDateFormat;
import java.util.ArrayDeque;
import java.util.Date;
import java.util.Locale;

/** Bounded, in-memory evidence log. Never pass pairing codes or raw packets here. */
final class SurveyActivityLog {
    private final ArrayDeque<String> entries=new ArrayDeque<>();
    private long revision=0;
    synchronized void add(long timestamp,String text){
        entries.addLast(new SimpleDateFormat("HH:mm:ss",Locale.getDefault()).format(new Date(timestamp))+"  "+text);
        while(entries.size()>100)entries.removeFirst();
        revision++;
    }
    synchronized long revision(){return revision;}
    synchronized String snapshot(){return String.join("\n\n",entries);}
}
