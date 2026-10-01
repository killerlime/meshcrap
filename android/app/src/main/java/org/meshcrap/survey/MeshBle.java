package org.meshcrap.survey;

import android.annotation.SuppressLint;
import android.bluetooth.*;
import android.content.Context;
import android.os.Handler;
import java.util.*;

/** Serialized GATT access. Only the caller's explicitly selected bonded radio is opened. */
@SuppressLint("MissingPermission")
final class MeshBle {
    interface Listener { void ready(); void received(byte[] data); void failed(String reason); }
    static final UUID SERVICE=UUID.fromString("6ba1b218-15a8-461f-9fa8-5dcae273eafd");
    static final UUID TO=UUID.fromString("f75c76d2-129e-4dad-a1dd-7866124401e7");
    static final UUID FROM=UUID.fromString("2c55e69e-4993-11ed-b878-0242ac120002");
    private final Handler h;private final Listener listener;private BluetoothGatt gatt;
    private BluetoothGattCharacteristic to,from;private boolean busy=false,closed=false;private int mtu=23;
    private final ArrayDeque<byte[]> writes=new ArrayDeque<>();
    private final Runnable timeout=()->fail("Bluetooth operation timed out. Reconnect when ready.");
    MeshBle(Context context,BluetoothDevice device,Handler handler,Listener l){
        h=handler;listener=l;gatt=device.connectGatt(context,false,callback,BluetoothDevice.TRANSPORT_LE);
        h.postDelayed(timeout,20000);
    }
    private void fail(String reason){if(closed)return;close();listener.failed(reason);}
    void close(){closed=true;h.removeCallbacks(timeout);h.removeCallbacks(poll);writes.clear();if(gatt!=null){gatt.disconnect();gatt.close();gatt=null;}}
    void send(byte[] data){if(closed||to==null)throw new IllegalStateException("Bluetooth is not ready");
        if(data.length>mtu-3||writes.size()>8)throw new IllegalStateException("Bluetooth write exceeds available capacity");
        writes.add(data);pump();
    }
    private final Runnable poll=()->{if(!closed)pump();};
    private void pump(){
        if(closed||busy||gatt==null||from==null)return;
        h.removeCallbacks(poll);busy=true;h.postDelayed(timeout,15000);
        boolean ok;
        if(!writes.isEmpty()){
            byte[] data=writes.remove();to.setValue(data);to.setWriteType(BluetoothGattCharacteristic.WRITE_TYPE_DEFAULT);ok=gatt.writeCharacteristic(to);
        }else ok=gatt.readCharacteristic(from);
        if(!ok)fail("Bluetooth refused an operation. Disconnect Meshtastic and reconnect here.");
    }
    private final BluetoothGattCallback callback=new BluetoothGattCallback(){
        public void onConnectionStateChange(BluetoothGatt g,int status,int state){h.post(()->{
            if(closed||g!=gatt)return;h.removeCallbacks(timeout);
            if(status!=BluetoothGatt.GATT_SUCCESS||state==BluetoothProfile.STATE_DISCONNECTED){fail("Bluetooth disconnected; automatic survey paused.");return;}
            if(state==BluetoothProfile.STATE_CONNECTED){h.postDelayed(timeout,20000);if(!g.requestMtu(512))fail("Unable to negotiate Bluetooth message size");}
        });}
        public void onMtuChanged(BluetoothGatt g,int size,int status){h.post(()->{
            if(closed||g!=gatt)return;h.removeCallbacks(timeout);
            if(status!=BluetoothGatt.GATT_SUCCESS||size<64){fail("This connection could not negotiate the required Bluetooth message size");return;}
            mtu=size;h.postDelayed(timeout,15000);if(!g.discoverServices())fail("Service discovery failed");
        });}
        public void onServicesDiscovered(BluetoothGatt g,int status){h.post(()->{
            if(closed||g!=gatt)return;h.removeCallbacks(timeout);BluetoothGattService service=g.getService(SERVICE);
            if(status!=BluetoothGatt.GATT_SUCCESS||service==null){fail("The selected device does not expose Meshtastic Bluetooth");return;}
            to=service.getCharacteristic(TO);from=service.getCharacteristic(FROM);
            if(to==null||from==null){fail("Meshtastic Bluetooth characteristics are missing");return;}
            listener.ready();pump();
        });}
        @Deprecated public void onCharacteristicRead(BluetoothGatt g,BluetoothGattCharacteristic c,int status){
            byte[] value=c.getValue();read(g,value==null?new byte[0]:value.clone(),status);
        }
        public void onCharacteristicRead(BluetoothGatt g,BluetoothGattCharacteristic c,byte[] value,int status){read(g,value.clone(),status);}
        private void read(BluetoothGatt g,byte[] value,int status){h.post(()->{
            if(closed||g!=gatt)return;h.removeCallbacks(timeout);busy=false;
            if(status!=BluetoothGatt.GATT_SUCCESS){fail("Bluetooth read failed ("+status+")");return;}
            if(value.length>0)listener.received(value);
            if(closed)return;
            if(!writes.isEmpty()||value.length>0)pump();else h.postDelayed(poll,1500);
        });}
        public void onCharacteristicWrite(BluetoothGatt g,BluetoothGattCharacteristic c,int status){h.post(()->{
            if(closed||g!=gatt)return;h.removeCallbacks(timeout);busy=false;
            if(status!=BluetoothGatt.GATT_SUCCESS){fail("Bluetooth write failed ("+status+")");return;}pump();
        });}
    };
}
