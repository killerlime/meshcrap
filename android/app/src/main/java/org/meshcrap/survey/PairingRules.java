package org.meshcrap.survey;

import java.net.URI;

/** Validate without ever reflecting the pairing secret in an error message. */
final class PairingRules {
    static void validateConnection(String url,String token){
        URI uri;
        try{uri=new URI(url);}catch(Exception e){throw new IllegalArgumentException("The collector address in this code is incomplete. Copy the full pairing code again.");}
        if(!"https".equalsIgnoreCase(uri.getScheme())||uri.getHost()==null||uri.getUserInfo()!=null
                ||(uri.getPort()!=-1&&uri.getPort()!=443)||!"/api/survey-phone/sync".equals(uri.getPath())
                ||uri.getQuery()!=null||uri.getFragment()!=null)
            throw new IllegalArgumentException("This code needs the collector's private HTTPS survey address. Copy it from the phone setup page.");
        if(token==null||!token.matches("[A-Za-z0-9_-]{32,128}"))
            throw new IllegalArgumentException("The pairing secret is incomplete or damaged. Copy the full phone pairing code, not the Bluetooth PIN or dashboard control key.");
    }
    static String validatePrefix(String value){
        String prefix=value==null?"":value.trim();
        if(!prefix.matches("[A-Za-z][A-Za-z0-9]{0,7}"))throw new IllegalArgumentException("Use the common beginning of your local radio names: 1–8 letters or numbers, starting with a letter.");
        return prefix;
    }
}
