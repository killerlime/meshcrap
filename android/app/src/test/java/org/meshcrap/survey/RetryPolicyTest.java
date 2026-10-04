package org.meshcrap.survey;
import org.junit.Test;
import static org.junit.Assert.*;
public class RetryPolicyTest {
 @Test public void onlyConfirmedFailuresRetryAndNeverMoreThanThree(){
  assertTrue(RetryPolicy.retryable("timeout",1,false));
  assertTrue(RetryPolicy.retryable("routing_error",2,false));
  assertFalse(RetryPolicy.retryable("timeout",3,false));
  assertFalse(RetryPolicy.retryable("transport_error",1,false));
  assertFalse(RetryPolicy.retryable("stopped",1,false));
 }
 @Test public void successIncludingLateSuccessPreventsFurtherRetries(){
  assertFalse(RetryPolicy.retryable("timeout",2,true));
  assertFalse(RetryPolicy.retryable("success",1,false));
  assertFalse(RetryPolicy.retryable("late_success",1,false));
 }
 @Test public void persistedDeadlineAndClockRollbackAreRespected(){
  assertFalse(RetryPolicy.eligible(1000,1030,1029));
  assertTrue(RetryPolicy.eligible(1000,1030,1030));
  assertFalse(RetryPolicy.eligible(1000,29800,29799));
  assertTrue(RetryPolicy.eligible(1000,29800,29800));
  assertFalse(RetryPolicy.eligible(1000,0,999));
 }
}
