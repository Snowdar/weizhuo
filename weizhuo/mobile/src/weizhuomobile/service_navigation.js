(() => {
  if (!['127.0.0.1','localhost'].includes(location.hostname)) return false;
  if (!document.body) return false;
  document.documentElement.classList.add('host-app');
  for(const [edge,value] of Object.entries(__SAFE_AREA__))document.documentElement.style.setProperty('--host-safe-'+edge,value+'px');
  if (!document.getElementById('weizhuo-service-nav')) {
    const host=document.createElement('div');host.id='weizhuo-service-nav';
    const shadow=host.attachShadow({mode:'open'});
    shadow.innerHTML=`<style>
      :host{position:fixed;left:8px;bottom:calc(max(env(safe-area-inset-bottom,0px),var(--host-safe-bottom,0px)) + 104px);z-index:2147483646}
      button{font:600 14px system-ui;color:#244d3d;background:#fffdf3;border:1px solid #c6d3bf;border-radius:22px;min-height:44px;padding:0 14px;box-shadow:0 2px 8px #0002;-webkit-user-select:none;user-select:none;-webkit-touch-callout:none;touch-action:manipulation;cursor:pointer;-webkit-tap-highlight-color:transparent}
      #toggle{width:44px;padding:0;font-size:21px} #back{margin-left:6px} [hidden]{display:none!important}
    </style><button id="toggle" aria-label="服务导航" aria-expanded="false">⌂</button><button id="back" hidden>返回服务首页</button>`;
    document.body.appendChild(host);
    const toggle=shadow.getElementById('toggle'),back=shadow.getElementById('back');
    toggle.onclick=()=>{back.hidden=!back.hidden;toggle.setAttribute('aria-expanded',String(!back.hidden));};
    back.onclick=()=>{window.__weizhuoReturnToService=true;back.hidden=true;toggle.setAttribute('aria-expanded','false');};
    document.addEventListener('pointerdown',e=>{if(!e.composedPath().includes(host)){back.hidden=true;toggle.setAttribute('aria-expanded','false');}},true);
  }
  const networkNotice=__NETWORK_NOTICE__;
  const navigation=document.getElementById('weizhuo-service-nav')?.shadowRoot;
  if(navigation){
    const back=navigation.getElementById('back'),toggle=navigation.getElementById('toggle');
    back.textContent=networkNotice||'返回服务首页';
    back.style.maxWidth='min(260px, calc(100vw - 76px))';
    back.style.whiteSpace='normal';
    back.style.padding='8px 14px';
    back.setAttribute('aria-live','polite');
    if(networkNotice&&networkNotice!==window.__weizhuoLastNetworkNotice){
      back.hidden=false;toggle.setAttribute('aria-expanded','true');
    }
    window.__weizhuoLastNetworkNotice=networkNotice;
  }
  const keyboard=__KEYBOARD__;if(JSON.stringify(window.__weizhuoKeyboard)!==JSON.stringify(keyboard)){window.__weizhuoKeyboard=keyboard;window.dispatchEvent(new Event('weizhuokeyboard'));}
  window.__weizhuoNativeSpeech=__NATIVE_SPEECH__;
  if (__NATIVE_SPEECH__) {
    const choices=__VOICE_CHOICES__,names={0:"清晰 · 系统",1:"松朗 · 男声",2:"悦然 · 女声",3:"暖语 · Serena"};
    if (!choices.includes(window.__weizhuoVoiceChoice))window.__weizhuoVoiceChoice=__VOICE_CHOICE__;
    const tools=document.querySelector('.table-detail-tools');
    if(tools?.querySelector('[data-host-sound]') && !tools.querySelector('[data-native-voice]')){
      const voice=document.createElement('select');voice.dataset.nativeVoice='true';voice.setAttribute('aria-label','选择播报音色');voice.innerHTML=choices.map(id=>`<option value="${id}">${names[id]}</option>`).join('');voice.value=String(window.__weizhuoVoiceChoice);
            voice.onchange=()=>{const selected=Number(voice.value);if(!choices.includes(selected))return;window.__weizhuoVoiceChoice=selected;const menu=tools.closest('.table-detail-menu');menu?.classList.remove('menu-open');menu?.querySelector('.table-menu-toggle')?.setAttribute('aria-expanded','false');tools.hidden=true;};
      tools.appendChild(voice);
      const audition=document.createElement('button');audition.type='button';audition.dataset.nativeAudition='true';audition.textContent='试听播报';
      audition.onclick=()=>{window.__weizhuoVoiceTest=true;window.__weizhuoAuditionUsed=true;};tools.appendChild(audition);
    }
  }
  const auditionButton=document.querySelector('[data-native-audition]');if(auditionButton && window.__weizhuoAuditionUsed)auditionButton.textContent='试听播报 · '+__VOICE_STATUS__;
  const queue=window.__weizhuoSpeechQueue||[];while(queue.length&&Date.now()-queue[0].at>120000)queue.shift();
  let speech='';
  if(!window.__weizhuoVoiceTest&&__SPEECH_READY__&&queue.length){
    const next=queue[0];
    if(next.readyAt===undefined){try{window.__weizhuoBeforeSpeech?.(next.score===true)}catch{};next.readyAt=Date.now()+300;}
    if(Date.now()>=next.readyAt)speech=queue.shift().text;
  }
  const audition=window.__weizhuoVoiceTest===true&&__SPEECH_READY__;if(audition)window.__weizhuoVoiceTest=false;
  const returned=window.__weizhuoReturnToService===true;
  window.__weizhuoReturnToService=false;
  return {tableLocked:document.documentElement.classList.contains('table-viewport'),returned,speech:audition?'三号玩家跟注二十分。三号玩家弃牌。本局已结算。':speech,audition,voice:window.__weizhuoVoiceChoice,quiet:document.hidden||window.__weizhuoSoundMuted===true};
})()
