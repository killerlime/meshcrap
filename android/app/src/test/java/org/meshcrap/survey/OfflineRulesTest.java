package org.meshcrap.survey;
import org.junit.Test;
import static org.junit.Assert.*;
public class OfflineRulesTest {
    private final String permit="a".repeat(43);
    @Test public void boundedAndRadioScoped(){
        assertTrue(OfflineRules.valid(2,3,3,100,86500,200,permit));
        assertFalse(OfflineRules.valid(2,3,4,100,86500,200,permit));
        assertFalse(OfflineRules.valid(0,3,3,100,86500,200,permit));
        assertFalse(OfflineRules.valid(2,3,3,100,86500,200,""));
    }
    @Test public void expiryAndClockRollbackStopRecording(){
        assertFalse(OfflineRules.valid(2,3,3,100,86500,86500,permit));
        assertFalse(OfflineRules.valid(2,3,3,100,86500,99,permit));
        assertFalse(OfflineRules.valid(2,3,3,100,86501,200,permit));
    }
    @Test public void retriesAreBounded(){
        assertEquals(15000,OfflineRules.retryDelay(0));assertEquals(30000,OfflineRules.retryDelay(1));
        assertEquals(60000,OfflineRules.retryDelay(2));assertEquals(60000,OfflineRules.retryDelay(10));
    }
}
