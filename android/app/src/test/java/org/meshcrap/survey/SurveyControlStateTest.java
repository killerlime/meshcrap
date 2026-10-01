package org.meshcrap.survey;
import org.junit.Test;
import static org.junit.Assert.*;
public class SurveyControlStateTest {
 @Test public void startNeedsConfirmationAndMatchingSync(){
  SurveyControlState s=new SurveyControlState();long command=s.begin();assertTrue(s.blocksRequests());
  s.complete(command,true,4);assertFalse(s.busy());assertTrue(s.blocksRequests());
  assertTrue(s.synced(4));assertFalse(s.blocksRequests());assertFalse(s.synced(4));
 }
 @Test public void pauseDuringStartCannotBeOverriddenByReply(){
  SurveyControlState s=new SurveyControlState();long command=s.begin();s.pause();
  s.complete(command,true,4);assertFalse(s.synced(4));
 }
 @Test public void pauseAfterConfirmationStillCancelsResume(){
  SurveyControlState s=new SurveyControlState();long command=s.begin();s.complete(command,true,4);
  s.pause();assertFalse(s.synced(4));
 }
 @Test public void endBlocksUntilRefreshedAndNeverResumes(){
  SurveyControlState s=new SurveyControlState();long command=s.begin();s.complete(command,false,4);
  assertTrue(s.blocksRequests());assertFalse(s.synced(0));assertFalse(s.blocksRequests());
 }
 @Test public void uncertainCommandNeedsSyncAndManualResume(){
  SurveyControlState s=new SurveyControlState();s.begin();s.failed();assertTrue(s.blocksRequests());
  assertFalse(s.synced(4));assertFalse(s.blocksRequests());
 }
 @Test public void replacementSurveyCannotAutoResume(){
  SurveyControlState s=new SurveyControlState();long command=s.begin();s.complete(command,true,4);
  assertFalse(s.synced(5));assertFalse(s.synced(4));
 }
}
