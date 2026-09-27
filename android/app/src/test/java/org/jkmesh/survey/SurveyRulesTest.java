package org.jkmesh.survey;
import org.junit.Test;
import static org.junit.Assert.*;
import org.meshtastic.proto.MeshProtos;
import org.meshtastic.proto.Portnums;
public class SurveyRulesTest {
 @Test public void neverBroadcastOrSelfUnknown(){assertFalse(SurveyRules.validId(0));assertFalse(SurveyRules.validId(0xffffffffL));assertTrue(SurveyRules.validId(305419896L));}
 @Test public void leaseAndCadenceGateEverySend(){
  assertTrue(SurveyRules.maySend(true,true,false,200000,70000,210000,1));
  assertFalse(SurveyRules.maySend(true,true,false,200000,90000,210000,1));
  assertFalse(SurveyRules.maySend(true,true,true,200000,70000,210000,1));
  assertFalse(SurveyRules.maySend(true,true,false,200000,70000,199999,1));
  assertFalse(SurveyRules.maySend(true,false,false,200000,70000,210000,1));
  assertFalse(SurveyRules.maySend(false,true,false,200000,70000,210000,1));
  assertFalse(SurveyRules.maySend(true,true,false,200000,70000,210000,0));
 }
 @Test public void geographicValidityAndFreshness(){assertFalse(SurveyRules.validPosition(Double.NaN,-94));assertFalse(SurveyRules.validPosition(0,0));assertFalse(SurveyRules.validPosition(91,0));assertTrue(SurveyRules.validPosition(44.2,-94));assertEquals(0,SurveyRules.miles(44,-94,44,-94),0.001);assertTrue(SurveyRules.miles(44,-94,45,-94)>68);assertFalse(SurveyRules.fresh(0,10000,300));assertFalse(SurveyRules.fresh(9000,10000,300));assertFalse(SurveyRules.fresh(10200,10000,300));assertTrue(SurveyRules.fresh(9900,10000,300));}
 @Test public void traceWireMessageDoesNotContainConfigWrites() throws Exception {
  var packet=MeshProtos.MeshPacket.newBuilder().setTo(0x12345678).setId(123).setChannel(0).setHopLimit(3).setWantAck(true).setDecoded(MeshProtos.Data.newBuilder().setPortnum(Portnums.PortNum.TRACEROUTE_APP).setWantResponse(true)).build();
  var wire=MeshProtos.ToRadio.newBuilder().setPacket(packet).build();var read=MeshProtos.ToRadio.parseFrom(wire.toByteArray());
  assertEquals(70,read.getPacket().getDecoded().getPortnumValue());assertEquals(0,read.getPacket().getFrom());assertTrue(read.getPacket().getDecoded().getWantResponse());assertEquals(305419896L,Integer.toUnsignedLong(read.getPacket().getTo()));assertEquals(0,read.getWantConfigId());
 }
}
