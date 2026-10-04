package org.meshcrap.survey;
import org.junit.Test;
import static org.junit.Assert.*;
import org.meshtastic.proto.MeshProtos;
import org.meshtastic.proto.Portnums;
public class SurveyRulesTest {
 @Test public void eightHourCooldownSurvivesSurveyAndChannelChanges(){
  assertTrue(SurveyRules.repeatEligible(0,1000));
  assertFalse(SurveyRules.repeatEligible(1000,999));
  assertFalse(SurveyRules.repeatEligible(1000,29799));
  assertTrue(SurveyRules.repeatEligible(1000,29800));
  var values=new java.util.HashMap<String,Object>();
  values.put("sample_123_10_0_456_time",1000L);
  values.put("sample_789_11_1_456_time",2000L);
  values.put("probe_456_time",1500L);
  values.put("sample_123_10_0_456_lat",9000L);
  var result=SurveyRules.migrateProbeTimes(values);
  assertEquals(1,result.size());assertEquals(Long.valueOf(2000),result.get("probe_456_time"));
 }

 @Test public void acknowledgmentCanOnlyRemoveSubmittedRecords(){
  java.util.Set<String> sent=new java.util.HashSet<>(java.util.Arrays.asList("one","two"));
  SurveyRules.validateAcknowledgments(sent,java.util.Arrays.asList("two"));
  SurveyRules.validateAcknowledgments(sent,java.util.Collections.emptyList());
  assertThrows(IllegalArgumentException.class,()->SurveyRules.validateAcknowledgments(sent,java.util.Arrays.asList("one","unsent")));
  assertThrows(IllegalArgumentException.class,()->SurveyRules.validateAcknowledgments(sent,java.util.Arrays.asList("one","one")));
 }
 @Test public void activityLogKeepsRecentEvidenceInOrder(){
  SurveyActivityLog log=new SurveyActivityLog();for(int i=0;i<101;i++)log.add(1000L*i,"Event "+i+" done");
  String text=log.snapshot();assertFalse(text.contains("Event 0 done"));assertTrue(text.contains("Event 1 done"));
  assertTrue(text.endsWith("Event 100 done"));assertEquals(101,log.revision());assertEquals(100,text.split("\n\n").length);
 }
 @Test public void neverBroadcastOrSelfUnknown(){assertFalse(SurveyRules.validId(0));assertFalse(SurveyRules.validId(0xffffffffL));assertTrue(SurveyRules.validId(305419896L));}
 @Test public void leaseAndCadenceGateEverySend(){
  assertTrue(SurveyRules.maySend(true,true,false,200000,70000,210000,1));
  assertFalse(SurveyRules.maySend(true,true,false,200000,170001,210000,1));
  assertTrue(SurveyRules.maySend(true,true,false,200000,170000,210000,1));
  assertFalse(SurveyRules.maySend(true,true,true,200000,70000,210000,1));
  assertFalse(SurveyRules.maySend(true,true,false,200000,70000,199999,1));
  assertFalse(SurveyRules.maySend(true,false,false,200000,70000,210000,1));
  assertFalse(SurveyRules.maySend(false,true,false,200000,70000,210000,1));
  assertFalse(SurveyRules.maySend(true,true,false,200000,70000,210000,0));
 }
 @Test public void restartedCadenceAndClockRollbackRemainBounded(){
  assertTrue(SurveyRules.cadenceBlocked(1000,1029));assertFalse(SurveyRules.cadenceBlocked(1000,1030));
  assertTrue(SurveyRules.cadenceBlocked(1000,900));assertFalse(SurveyRules.cadenceBlocked(0,10));
 }
 @Test public void movingPositionMustBeCurrent(){
  assertTrue(SurveyRules.travellingPositionFresh(13600,100000));assertFalse(SurveyRules.travellingPositionFresh(13599,100000));
  assertFalse(SurveyRules.travellingPositionFresh(1001,1000));assertFalse(SurveyRules.travellingPositionFresh(0,1000));
 }
 @Test public void halfMileAccuracyBoundary(){
  assertTrue(SurveyRules.travellingAccuracyValid(804.672));assertFalse(SurveyRules.travellingAccuracyValid(804.673));
  assertFalse(SurveyRules.travellingAccuracyValid(-1));assertFalse(SurveyRules.travellingAccuracyValid(Double.NaN));
  assertFalse(SurveyRules.travellingAccuracyValid(Double.POSITIVE_INFINITY));
 }
 @Test public void candidatesUseFixAgeSeparatelyFromLastHeard(){
  assertFalse(SurveyRules.candidateFresh(56799,0,100000,2));
  assertTrue(SurveyRules.candidateFresh(56800,0,100000,2));
  assertTrue(SurveyRules.candidateFresh(1,999,1000,1));
  assertTrue(SurveyRules.candidateFresh(999,0,1000,1));
  assertFalse(SurveyRules.candidateFresh(1001,999,1000,2));
  assertFalse(SurveyRules.automaticCandidate(0,32));assertFalse(SurveyRules.automaticCandidate(2,0));
  assertFalse(SurveyRules.automaticCandidate(2,19));assertTrue(SurveyRules.automaticCandidate(2,20));
  assertTrue(SurveyRules.automaticCandidate(1,32));assertFalse(SurveyRules.automaticCandidate(2,33));
 }
 @Test public void geographicValidityAndFreshness(){assertFalse(SurveyRules.validPosition(Double.NaN,-94));assertFalse(SurveyRules.validPosition(0,0));assertFalse(SurveyRules.validPosition(91,0));assertTrue(SurveyRules.validPosition(44.2,-94));assertEquals(0,SurveyRules.miles(44,-94,44,-94),0.001);assertTrue(SurveyRules.miles(44,-94,45,-94)>68);assertFalse(SurveyRules.fresh(0,10000,300));assertFalse(SurveyRules.fresh(9000,10000,300));assertFalse(SurveyRules.fresh(10200,10000,300));assertTrue(SurveyRules.fresh(9900,10000,300));}
 @Test public void traceWireMessageDoesNotContainConfigWrites() throws Exception {
  var packet=MeshProtos.MeshPacket.newBuilder().setTo(0x12345678).setId(123).setChannel(0).setHopLimit(3).setWantAck(true).setDecoded(MeshProtos.Data.newBuilder().setPortnum(Portnums.PortNum.TRACEROUTE_APP).setWantResponse(true)).build();
  var wire=MeshProtos.ToRadio.newBuilder().setPacket(packet).build();var read=MeshProtos.ToRadio.parseFrom(wire.toByteArray());
  assertEquals(70,read.getPacket().getDecoded().getPortnumValue());assertEquals(0,read.getPacket().getFrom());assertTrue(read.getPacket().getDecoded().getWantResponse());assertEquals(305419896L,Integer.toUnsignedLong(read.getPacket().getTo()));assertEquals(0,read.getWantConfigId());
 }
}
