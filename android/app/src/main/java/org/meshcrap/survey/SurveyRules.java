package org.meshcrap.survey;

/** Pure survey rules, independently testable without Android or a radio. */
public final class SurveyRules {
    public static final long SPACING_MS=120_000, TIMEOUT_MS=120_000, LEASE_MS=30_000;
    private SurveyRules() {}
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
    public static boolean maySend(boolean ready,boolean meshcrap,boolean pending,long now,long lastSent,long leaseUntil,long survey) {
        return ready&&meshcrap&&!pending&&survey>0&&now<leaseUntil&&(lastSent==0||now-lastSent>=SPACING_MS);
    }
}
