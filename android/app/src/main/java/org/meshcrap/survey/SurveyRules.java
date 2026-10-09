package org.meshcrap.survey;

/** Pure survey rules, independently testable without Android or a radio. */
public final class SurveyRules {
    public static final long SPACING_MS=30_000, TIMEOUT_MS=30_000, LEASE_MS=30_000;
    public static final long POSITION_MAX_AGE_SECONDS=86400;
    public static final long CANDIDATE_GPS_MAX_AGE_SECONDS=7*86400;
    public static final double POSITION_MAX_ACCURACY_METRES=804.672;
    private SurveyRules() {}
    public static boolean repeatEligible(long previous,long now) {
        return previous<=0 || (now>=previous && now-previous>=28800);
    }
    public static java.util.Map<String,Long> migrateProbeTimes(java.util.Map<String,?> values) {
        java.util.Map<String,Long> migrated=new java.util.HashMap<>();
        for(var entry:values.entrySet()) {
            if(!(entry.getValue() instanceof Long))continue;
            String key=entry.getKey();
            if(key.matches("sample_-?[0-9]+_[0-9]+_[0-9]+_-?[0-9]+_time")) {
                String[] parts=key.split("_");key="probe_"+parts[4]+"_time";
            } else if(!key.matches("probe_-?[0-9]+_time"))continue;
            migrated.merge(key,(Long)entry.getValue(),Math::max);
        }
        return migrated;
    }
    public static boolean validId(long id) { return id>0 && id<0xffffffffL; }
    public static boolean validPosition(double lat,double lon) {
        return Double.isFinite(lat)&&Double.isFinite(lon)&&lat>=-90&&lat<=90&&lon>=-180&&lon<=180&&(lat!=0||lon!=0);
    }
    public static double miles(double a,double b,double c,double d) {
        double p=Math.toRadians(c-a),q=Math.toRadians(d-b);
        double x=Math.sin(p/2)*Math.sin(p/2)+Math.cos(Math.toRadians(a))*Math.cos(Math.toRadians(c))*Math.sin(q/2)*Math.sin(q/2);
        return 3958.7613*2*Math.asin(Math.sqrt(Math.min(1,Math.max(0,x))));
    }
    public static boolean fresh(long timestampSeconds,long nowSeconds,long maxAge) {
        return timestampSeconds>0 && timestampSeconds<=nowSeconds+120 && nowSeconds-timestampSeconds<=maxAge;
    }
    public static boolean travellingPositionFresh(long timestampSeconds,long nowSeconds) {
        // Future coordinates are not a current fix, even within upload clock-skew tolerance.
        return timestampSeconds>0 && timestampSeconds<=nowSeconds && nowSeconds-timestampSeconds<=POSITION_MAX_AGE_SECONDS;
    }
    public static boolean travellingAccuracyValid(double metres) {
        return Double.isFinite(metres)&&metres>=0&&metres<=POSITION_MAX_ACCURACY_METRES;
    }
    public static boolean cadenceBlocked(long lastEpoch,long nowEpoch) {
        return lastEpoch>0 && (nowEpoch<lastEpoch || nowEpoch-lastEpoch<SPACING_MS/1000);
    }
    public static boolean candidateFresh(long positionTime,long heardTime,long now,int source) {
        // Discovery uses advertised coordinates, not proof of a current location.
        // Fixed/manual and unknown-source coordinates do not expire with node activity.
        // Zero means the radio did not provide the original position time.
        if(source<0||source>3||positionTime<0||positionTime>now)return false;
        return positionTime==0||source==0||source==1||now-positionTime<=CANDIDATE_GPS_MAX_AGE_SECONDS;
    }
    public static boolean automaticCandidate(int source,int precisionBits) {
        // Resolution/source are disclosed in the UI and recorded with the request.
        // Missing or coarse metadata must not suppress otherwise usable discovery.
        return source>=0 && source<=3 && precisionBits>=0 && precisionBits<=32;
    }
    public static String candidateAgeLabel(long positionTime,long now) {
        if(positionTime<=0)return "position age unknown";
        long age=Math.max(0,now-positionTime);
        if(age<60)return "position "+age+"s old";
        if(age<3600)return "position "+(age/60)+" min old";
        if(age<86400)return "position "+(age/3600)+" hr old";
        return "position "+(age/86400)+" days old";
    }
    public static boolean traceStorageAvailable(int queued,int limit) {
        // Reserve room for request/result records and late responses near capacity.
        return queued>=0&&limit>10&&queued<limit-10;
    }
    public static void validateAcknowledgments(java.util.Set<String> submitted,java.util.List<String> accepted) {
        java.util.Set<String> seen=new java.util.HashSet<>();
        for(String id:accepted)if(!submitted.contains(id)||!seen.add(id))throw new IllegalArgumentException("Invalid upload acknowledgment");
    }
    public static boolean maySend(boolean ready,boolean meshcrap,boolean pending,long now,long lastSent,long leaseUntil,long survey) {
        return ready&&meshcrap&&!pending&&survey>0&&now<leaseUntil&&(lastSent==0||now-lastSent>=SPACING_MS);
    }
}
