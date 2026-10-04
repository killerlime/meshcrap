package org.meshcrap.survey;

/** Pure survey rules, independently testable without Android or a radio. */
public final class SurveyRules {
    public static final long SPACING_MS=30_000, TIMEOUT_MS=30_000, LEASE_MS=30_000;
    public static final long POSITION_MAX_AGE_SECONDS=3600;
    public static final double POSITION_MAX_ACCURACY_METRES=804.672;
    private SurveyRules() {}
    public static boolean repeatEligible(long previous,long now,double movedMiles,boolean precise) {
        if(previous<=0)return true;
        if(now<previous||now-previous<60)return false;
        return now-previous>=300 || (precise&&Double.isFinite(movedMiles)&&movedMiles>=0.5);
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
        long age=source==1?86400:300; // Manual/installed coordinates are not live GPS.
        return positionTime>0 && positionTime<=now && now-positionTime<=age
            && heardTime>0 && heardTime<=now && now-heardTime<=900;
    }
    public static boolean automaticCandidate(int source,int precisionBits) {
        // Missing precision is unknown, not an assurance of full accuracy.
        return source>=1 && source<=3 && precisionBits>=20 && precisionBits<=32;
    }
    public static void validateAcknowledgments(java.util.Set<String> submitted,java.util.List<String> accepted) {
        java.util.Set<String> seen=new java.util.HashSet<>();
        for(String id:accepted)if(!submitted.contains(id)||!seen.add(id))throw new IllegalArgumentException("Invalid upload acknowledgment");
    }
    public static boolean maySend(boolean ready,boolean meshcrap,boolean pending,long now,long lastSent,long leaseUntil,long survey) {
        return ready&&meshcrap&&!pending&&survey>0&&now<leaseUntil&&(lastSent==0||now-lastSent>=SPACING_MS);
    }
}
