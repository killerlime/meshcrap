package org.meshcrap.survey;

import android.content.Context;
import android.util.Base64;
import android.security.keystore.KeyGenParameterSpec;
import android.security.keystore.KeyProperties;
import java.security.KeyStore;
import javax.crypto.Cipher;
import javax.crypto.KeyGenerator;
import javax.crypto.SecretKey;
import javax.crypto.spec.GCMParameterSpec;

final class PrivateStore {
    private static SecretKey key() throws Exception {
        KeyStore ks=KeyStore.getInstance("AndroidKeyStore");ks.load(null);
        if(!ks.containsAlias("meshcrap-survey")) {
            KeyGenerator gen=KeyGenerator.getInstance("AES","AndroidKeyStore");
            gen.init(new KeyGenParameterSpec.Builder("meshcrap-survey",KeyProperties.PURPOSE_ENCRYPT|KeyProperties.PURPOSE_DECRYPT)
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM).setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE).build());gen.generateKey();
        }
        return (SecretKey)ks.getKey("meshcrap-survey",null);
    }
    static void save(Context c,String value)throws Exception {
        save(c,"pairing",value);
    }
    static void save(Context c,String slot,String value)throws Exception {
        Cipher cipher=Cipher.getInstance("AES/GCM/NoPadding");cipher.init(Cipher.ENCRYPT_MODE,key());
        String stored=Base64.encodeToString(cipher.getIV(),Base64.NO_WRAP)+":"+Base64.encodeToString(cipher.doFinal(value.getBytes(java.nio.charset.StandardCharsets.UTF_8)),Base64.NO_WRAP);
        if(!c.getSharedPreferences("private",0).edit().putString(slot,stored).commit())throw new java.io.IOException("Could not save private state");
    }
    static String read(Context c)throws Exception {
        return read(c,"pairing");
    }
    static String read(Context c,String slot)throws Exception {
        String s=c.getSharedPreferences("private",0).getString(slot,"");if(s.isEmpty())return "";
        String[] parts=s.split(":",2);Cipher cipher=Cipher.getInstance("AES/GCM/NoPadding");
        cipher.init(Cipher.DECRYPT_MODE,key(),new GCMParameterSpec(128,Base64.decode(parts[0],Base64.NO_WRAP)));
        return new String(cipher.doFinal(Base64.decode(parts[1],Base64.NO_WRAP)),java.nio.charset.StandardCharsets.UTF_8);
    }
}
