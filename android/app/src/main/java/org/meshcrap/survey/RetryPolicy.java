package org.meshcrap.survey;

/** Persist every transition before sending; uncertain sends keep their cooldown. */
final class RetryPolicy {
    static final long COOLDOWN=28800, RETRY_DELAY=30;
    static boolean eligible(long last,long next,long now){return now>=last && now>=next;}
    static boolean retryable(String outcome,int count,boolean succeeded){
        return !succeeded && count<3 && (outcome.equals("timeout") || outcome.equals("routing_error"));
    }
}
