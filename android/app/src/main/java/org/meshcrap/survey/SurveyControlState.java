package org.meshcrap.survey;

/** Main-thread state: a command must settle and sync before requests can resume. */
final class SurveyControlState {
    private long revision=0,resumeSurvey=0;
    private boolean busy=false,awaitingSync=false;
    void pause(){revision++;resumeSurvey=0;}
    long begin(){pause();busy=true;return revision;}
    void complete(long commandRevision,boolean start,long survey){
        busy=false;awaitingSync=true;
        resumeSurvey=start&&commandRevision==revision?survey:0;
    }
    void failed(){busy=false;awaitingSync=true;pause();}
    boolean synced(long survey){
        boolean resume=awaitingSync&&resumeSurvey>0&&resumeSurvey==survey;
        awaitingSync=false;resumeSurvey=0;return resume;
    }
    boolean busy(){return busy;}
    boolean blocksRequests(){return busy||awaitingSync;}
}
