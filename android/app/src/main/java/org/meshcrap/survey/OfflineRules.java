package org.meshcrap.survey;

/** A bounded, collector-issued authorization; wall-clock rollback fails closed. */
final class OfflineRules {
    static boolean valid(long survey,int source,int currentSource,long issued,long expires,long now,String permit) {
        return survey>0&&source!=0&&source==currentSource&&issued>0&&now>=issued&&now<expires
            &&expires-issued<=86400&&permit!=null&&permit.length()>=32&&permit.length()<=128;
    }
    static long retryDelay(int failures) {return failures==0?15000:Math.min(60000,15000L<<Math.min(2,failures));}
}
