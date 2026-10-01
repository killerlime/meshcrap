/* Numeric facts only; original summaries. Reviewed 2026-10-01. No vendor assets. */
(function(root){
 'use strict';
 const profiles={
  custom:{name:'Custom / other supported device',power:null,band:null,note:'Enter measured or documented values for the exact radio and region.',source:'https://meshtastic.org/docs/hardware/devices/'},
  rak:{name:'RAK4631 · high-band variant',power:22,band:[863,928],note:'SX1262; published maximum TX 22 dBm. Receiver sensitivity at your preset remains user-supplied.',source:'https://store.rakwireless.com/products/rak4631-lpwan-node'},
  heltec:{name:'Heltec WiFi LoRa 32 V3 · 863–928 MHz',power:21,band:[863,928],sensitivity:-134,sf:12,bw:125,note:'SX1262. TX nominal maximum 21 ±1 dBm. Published sensitivity −134 dBm only at SF12 / 125 kHz; other settings require an estimate or measurement.',source:'https://heltec.org/project/wifi-lora-32-v3/'},
  g2:{name:'B&Q Station G2',power:35,band:[864,928],note:'SX1262 plus PA and LNA. 35 dBm is the published PA capability, not a recommended setting or measured output. Firmware and regional limits may be lower.',source:'https://meshtastic.org/docs/hardware/devices/b-and-q-consulting/station-series/'},
  g3:{name:'B&Q Station G3 · BQ35LORA900V1M',power:35,band:[850,930],note:'Published non-boost capability 35 dBm; SX1262 with dynamic LNA. Vendor page contains conflicting band/peak-power figures and a revision warning. 850–930 MHz uses its RF daughterboard description; verify your revision. Do not add internal LNA gain twice.',source:'https://pro.bqvoy.com/product/meshtastic-mesh-device-station-edition/'},
  muzi:{name:'Muzi Works · specify exact model',power:null,band:null,note:'H1, R1, R1 Neo and BASE are different designs. Select the underlying board only after confirming the model; no universal Muzi power/sensitivity assumption.',source:'https://muzi.works/pages/resources'},
  yeti:{name:'Yeti Wurks RAK-based station · verify kit',power:null,band:null,gain:3,note:'Vendor describes a RAK-based kit with a 915 MHz 3 dBi dipole. Kit revision and radio output require confirmation. Only antenna gain is populated.',source:'https://www.yetiwurks.com/product/yeti-wurks-meshtastic-basestation/'}
 };
 if(typeof module!=='undefined'&&module.exports)module.exports=profiles;else root.RadioHardware=profiles;
})(globalThis);
