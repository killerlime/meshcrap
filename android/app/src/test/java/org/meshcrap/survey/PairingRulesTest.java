package org.meshcrap.survey;
import org.junit.Test;
import static org.junit.Assert.*;
public class PairingRulesTest {
 private static final String TOKEN="a_test_token_with_32_characters_minimum";
 @Test public void olderCodeCanValidateBeforePrefixIsKnown(){
  PairingRules.validateConnection("https://collector.example/api/survey-phone/sync",TOKEN);
  assertEquals("MY",PairingRules.validatePrefix(" MY "));
 }
 @Test public void explicitHttpsPortIsAllowed(){PairingRules.validateConnection("https://collector.example:443/api/survey-phone/sync",TOKEN);}
 @Test public void unsafeAddressesStillFail(){
  for(String url:new String[]{"http://collector.example/api/survey-phone/sync","https://user@collector.example/api/survey-phone/sync","https://collector.example:8080/api/survey-phone/sync","https://collector.example/api/survey-phone/sync?secret=value","https://collector.example/api/survey-phone/sync#fragment","https://collector.example/","not an address"})
   assertThrows(IllegalArgumentException.class,()->PairingRules.validateConnection(url,TOKEN));
 }
 @Test public void damagedSecretsFailWithoutBeingReflected(){
  for(String token:new String[]{"123456",TOKEN+"\nheader",TOKEN+" ",""}){
   IllegalArgumentException e=assertThrows(IllegalArgumentException.class,()->PairingRules.validateConnection("https://collector.example/api/survey-phone/sync",token));
   if(!token.isEmpty())assertFalse(e.getMessage().contains(token));
  }
 }
 @Test public void missingOrInvalidPrefixCannotBeSilentlyAssumed(){
  for(String prefix:new String[]{"","123","TOO_LONG_NAME","@@NODE_PREFIX@@"})assertThrows(IllegalArgumentException.class,()->PairingRules.validatePrefix(prefix));
 }
}
