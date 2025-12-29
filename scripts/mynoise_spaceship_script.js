


// Cleverly designed, badly programmed by Stephane Pigeon 
// (c) Dr. Ir. Stephane Pigeon - myNoise.net 2013-25 - stephane at mynoise.net
// Last update 2025-12-26

var iNUMBERBANDS=10;
var bCALIBRATE=0;
var bMUTE=0;
var bMUTEsaved=0;
var bANIMATE=0;
var bDISABLED=0;
var bMEDITATIONSESSION=0;
var bFINISHEDLOADING=0;
var bSUPPORTOGG=0;
var bSUPPORTMP3=0;
var bSUSPENDED=0;
var bSTARTMUTED=0;
var sSYNCHRO="0123456789";
var bPITCHRAN=0;
var bOSAUTO=0;
var bEQ=0;
var bWAVEVISUALIZER=0;
var iINITIALANIMATIONSPEED=32;
var fMASTERGAIN=0.7;
var fTARGETSLIDERLEVEL=0.5; // average slider level when loading a preset
var fAUDIOFADETIME=0.1;
var timeOutOS=new Array();
var iTimer=-1;
var iMTimer=-1;
var epoch=0;
var fileExt=".mp3";
var voiceover=new Array();
var allContents;
var sto=new Array();
var fCONTEXTSTART;
var fLevelMultiplier=1.1;
var iAnimationFactor=1;
var iAnimationMode="s";
var iCurrentAnimationSpeed=iINITIALANIMATIONSPEED;
var timerTimeout, modulationTimeout, fadeTimeOut, meditationInterval, meditationInterval2, osInterval;
var interval=new Array();
var nextA=new Array();
var nextB=new Array();
var lastPlayedA=new Array();
var lastPlayedB=new Array();
var lastPlayedOS=[1,1,1,1,1,1,1,1,1,1];
var randomCounter=0;
var currentLevel=new Array();
var savedCurrentLevel=new Array();
var savedLevel=new Array();
var randomLevel=new Array();
var animationProfileLow=[0,0,0,0,0,0,0,0,0,0];
var animationProfileHigh=[0.5,0.5,0.5,0.5,0.5,0.5,0.5,0.5,0.5,0.5];
var bANIMATIONPROFILESET=0;
var bANIMATIONUSERPROFILESET=0;
var cloneURL, cookieURL, appShareURL;
var detune="0";
if (detune.length<2) detune=parseInt(detune);
var selSliders=[1,1,1,1,1,1,1,1,1,1,0];
var playbackFactor=new Array();
var iNowMovingTo=0;
var iFadeState=0;
var mmMin, mmMax;
	mmMin=1;
	mmMax=0;
var nzSliderIndex=new Array();
var lastSlider;
var uIDS="";
var pitchTable=[1];
var meditationBell, bogus;
var URLlevels="";
var URLanimate="";
var URLmute="";
var URLbell="";
var URLtimer="";
var URLdetune="";
var URLmagic="";
var URLtitle="";
var URLwidth="";
var URLanimateProfileLo="";
var URLanimateProfileHigh="";
var bDOWNLOADED=new Array();
var iSTARTED=new Array();
var iLOADED=new Array();
var iTOTAL=new Array();
var totSizeMP3=5385342;
var totSizeOGG=3755798;
var serverTotal=totSizeMP3;
var dlMonitorThrottle=-500;
var averageSliderLevel=0.4;
var samplesArray;
var longPressTimer;
var isLongPress=false;
var fSTEREOWIDTH=1;
var gainForEQ=1;
var animatedIndices=[];
var MOBILE=false;

function enableButton(ids,bEnable) {
    const method=bEnable?"removeClass":"addClass";
    const pointer=bEnable?"auto":"none";
    for (const id of ids) {
        const el=document.getElementById(id);
        if (el) {
            el.style.pointerEvents=pointer;
            $("#"+id)[method]("disabled");
        }
    }
}

function activateButton(ids,bActivate) { 
    const method=bActivate?"addClass":"removeClass";
    for (const id of ids) {
        $("#"+id)[method]("active");
    }
}

function msg(content) {
    if (!bSUSPENDED) {
        document.getElementById("msg").innerHTML=content;
    }
}

var stretch=[1.7,1.7,1.7,1.7,1.7,1.7,1.7,1.7,1.7,1.7];

// Web Audio API

var  sourceFileA = new Array();
var  sourceFileB = new Array();
var  sourceA = new Array();
var  sourceB = new Array();
var  l = new Array();
var  movedSlider;
var  masterGain;
var  faderGain;
var  dynCompressor;

// Nodes for MS Coding/Decoding
var splitterNode = null;
var mergerNode = null;
var midGain = null;
var sideGain = null;
var inverterGain = null;
var invertedSide = null;


function getUrlVars(str) {
    str=str||window.location.href; // if empty, use URL
    const vars={};
    str.replace(/[?&]+([^=&]+)=([^&]*)/gi,(m,key,value)=>{
        vars[key]=value;
    });
    return vars;
}

// SOUNDS

function assignSources(){

	if (bSUPPORTOGG) fileExt=".ogg";
		
	console.log('with '+fileExt+' files');
	console.log('Code : SPACESHIP');
	
	// Initialize the bell sound
	meditationBell = new Audio('/Audio/bell' + fileExt);
	meditationBell.preload = 'auto';

	// Generate source files A and B dynamically
	sourceFileA = [];
	sourceFileB = [];
	
	sourceFileA[0] = 'https://mynoise.world/Data/SPACESHIP/0b' + fileExt;
sourceFileB[0] = 'https://mynoise.world/Data/SPACESHIP/0a' + fileExt;
sourceFileA[1] = 'https://mynoise.world/Data/SPACESHIP/1b' + fileExt;
sourceFileB[1] = 'https://mynoise.world/Data/SPACESHIP/1a' + fileExt;
sourceFileA[2] = 'https://mynoise.world/Data/SPACESHIP/2a' + fileExt;
sourceFileB[2] = 'https://mynoise.world/Data/SPACESHIP/2b' + fileExt;
sourceFileA[3] = 'https://mynoise.world/Data/SPACESHIP/3b' + fileExt;
sourceFileB[3] = 'https://mynoise.world/Data/SPACESHIP/3a' + fileExt;
sourceFileA[4] = 'https://mynoise.world/Data/SPACESHIP/4a' + fileExt;
sourceFileB[4] = 'https://mynoise.world/Data/SPACESHIP/4b' + fileExt;
sourceFileA[5] = 'https://mynoise.world/Data/SPACESHIP/5b' + fileExt;
sourceFileB[5] = 'https://mynoise.world/Data/SPACESHIP/5a' + fileExt;
sourceFileA[6] = 'https://mynoise.world/Data/SPACESHIP/6a' + fileExt;
sourceFileB[6] = 'https://mynoise.world/Data/SPACESHIP/6b' + fileExt;
sourceFileA[7] = 'https://mynoise.world/Data/SPACESHIP/7a' + fileExt;
sourceFileB[7] = 'https://mynoise.world/Data/SPACESHIP/7b' + fileExt;
sourceFileA[8] = 'https://mynoise.world/Data/SPACESHIP/8b' + fileExt;
sourceFileB[8] = 'https://mynoise.world/Data/SPACESHIP/8a' + fileExt;
sourceFileA[9] = 'https://mynoise.world/Data/SPACESHIP/9a' + fileExt;
sourceFileB[9] = 'https://mynoise.world/Data/SPACESHIP/9b' + fileExt;
}

// WEBAUDIO LOADER
var  gainNode = new Array();
var  stemAnalyser = new Array();
var  eqNode = new Array();
var  bufferList = new Array();
var  loadCount=0;
var  context;

function loadWebAudioSound(url,i) {
    var request=new XMLHttpRequest();
    request.open('GET',url,true);
    request.responseType='arraybuffer';

    // See https://javascript.info/xmlhttprequest
    request.onload=function() {
        context.decodeAudioData(request.response,function(decodedData) {
            bufferList[i]=decodedData;
            countIn(i);
        });
    };

    request.onerror=function() {
        console.log('Problem detected >>> loading audio file from origin server instead.');
        var cdn="https://mynoise.world";
        if (url.indexOf(cdn)>-1) {
            url=url.substring(cdn.length);
            loadWebAudioSound(url,i); // load from one.com
        }
    };

    request.onprogress=function(event) {
        // ++ throttling every xxxms
        if (!this.NextSecond) this.NextSecond=0;
        if (Date.now()<this.NextSecond) return;
        this.NextSecond=Date.now()+dlMonitorThrottle;
        if (dlMonitorThrottle<1000) dlMonitorThrottle++;
        // ++
        dlMonitor(i,event,request,url);
    };

    bDOWNLOADED[i]=0;
    iSTARTED[i]=Date.now();

    request.send();
}


function resumeContext() {
	if (bSUSPENDED==1) {
		// we deliberately suspended the context
		bSUSPENDED=0;
		context.resume();
		if ("mediaSession" in navigator) navigator.mediaSession.playbackState="playing";
		$("#mute").unbind("click");
		$("#mute").click(toggleMute);
		nowPlaying();
	}
	else {
		// the context could be already running, or be suspended against our will (like phone lock-screen)
		if (context.state !== 'running') context.resume();
	}
	console.log("Audio Engine: resumed");
}

function nowPlaying() {
    if (bCALIBRATE==0) {
        msg("Now Playing...");
    } else {
        msg("1.&nbsp;Turn up your computer volume until you hear the static 2.&nbsp;Adjust each slider individually.");
    }
    enableButton(["reset","anim","volDown","volUp","mute","fftCanvas","timer","bell","calib","play0","play1","play2","play3","play4","play5","play6","play7","play8","play9"],1);
    if (bCALIBRATE==0) {
        document.getElementById("mute").style.display="none";
        document.getElementById("fftCanvas").style.display="block";
    }

    enableSliders();}

function loadAllSounds() {
    for (let i=0; i<iNUMBERBANDS; ++i) {
        loadWebAudioSound(sourceFileA[i],i);
    }
    for (let i=0; i<iNUMBERBANDS; ++i) {
        loadWebAudioSound(sourceFileB[i],i+iNUMBERBANDS);
    }
}

function playAllSounds() {
    for (let i=0; i<iNUMBERBANDS; ++i) {
        startWebAudio(i);
    }
}

function playOS(stem){
	var colorTable=["100,50,0","200,0,0","255,128,0","150,190,0","0,200,0","0,200,170","0,140,220","0,0,255","140,0,170","200,140,255"];
	var duration=0;
	playbackFactor[stem]= pitchTable[Math.floor(Math.random() * pitchTable.length)]
	if (lastPlayedOS[stem]) {
		webAudioPlayBAt(stem,context.currentTime);
		duration=sourceB[stem].buffer.duration;
		msg($('#s'+stem).attr('aria-label')+' • A • '+playbackFactor[stem]);
		}
	else {
		webAudioPlayAAt(stem,context.currentTime);
		duration=sourceA[stem].buffer.duration;
		msg($('#s'+stem).attr('aria-label')+' • B • '+playbackFactor[stem]);
	}
	lastPlayedOS[stem]=1-lastPlayedOS[stem];
	$("#play"+stem).css('background', 'rgb('+colorTable[stem]+')');
	clearTimeout(timeOutOS[stem]);	
	timeOutOS[stem]=setTimeout(function(){
		$("#play"+stem).css('background', 'rgba(0,0,0,0)');
		if (bOSAUTO) { playOS(Math.floor(Math.random()*10)); }
		},duration*1000/playbackFactor[stem]);
	
}

function experimentalPitchRandom(){
	bPITCHRAN++;
	if (bPITCHRAN==7) bPITCHRAN=0;
	switch(bPITCHRAN){
	case 0: pitchTable=[1]; msg('<span class="lowlight">'+pitchTable.toString().replace(/,/g,' ')+'</span>'); break;
	case 1: pitchTable=[0.5]; msg('<span class="lowlight">'+pitchTable.toString().replace(/,/g,' ')+'</span>'); break;
	case 2: pitchTable=[2]; msg('<span class="lowlight">'+pitchTable.toString().replace(/,/g,' ')+'</span>'); break;
	case 3: pitchTable=[0.5,1]; msg('<span class="lowlight">'+pitchTable.toString().replace(/,/g,' ')+'</span>'); break;
	case 4: pitchTable=[0.5,1,2]; msg('<span class="lowlight">'+pitchTable.toString().replace(/,/g,' ')+'</span>'); break;
	case 5: pitchTable=[0.5,1,1.5]; msg('<span class="lowlight">'+pitchTable.toString().replace(/,/g,' ')+'</span>'); break;
	case 6: pitchTable=[0.5,1,1.5,2]; msg('<span class="lowlight">'+pitchTable.toString().replace(/,/g,' ')+'</span>'); break;
	case 7: pitchTable=[0.5,0.75,1,1.5,2]; msg('<span class="lowlight">'+pitchTable.toString().replace(/,/g,' ')+'</span>'); break;
	}
}

function startWebAudio(i) {
    if (stretch[i]==0) sourceA[i].loop=1;
    nextA[i]=Math.ceil(context.currentTime);

    // take duration of the leader of the sync group
    const j=sSYNCHRO.indexOf(sSYNCHRO.charAt(i));
    nextB[i]=nextA[i]+Math.round(sourceA[j].buffer.duration*10)/20*stretch[j]/playbackFactor[j];

    sourceA[i].start(nextA[i]);
    lastPlayedA[i]=nextA[i];

    if (stretch[i]!=0) {
        webAudioPlayBAt(i,nextB[i]);
        lastPlayedB[i]=nextB[i];
    } else {
        sourceB[i].loop=1;
        sourceB[i].playbackRate.value=playbackFactor[i];
        sourceB[i].start(nextA[i]);
        lastPlayedB[i]=nextA[i];
    }
}

function computeIntervals(){
	// stems repeat every ((A+B)/2)*stretch and B starts after A/2*stretch - see doc. 
	var durA, durB;
	for (var i = 0; i < iNUMBERBANDS; ++i) {
		// buffer durations vary across browsers! Critical for sync gens, rounding off to 16th note
		durA=Math.round(sourceA[i].buffer.duration*8)/8;
		durB=Math.round(sourceB[i].buffer.duration*8)/8;
		interval[i]=(durA+durB)/2*stretch[i]/playbackFactor[i];
	}
}

function webAudioPlayAAt(item,onContextTime){

	// console.log('A@ '+context.currentTime+' for '+onContextTime+' on stem '+item);

	if (item==sSYNCHRO.indexOf(sSYNCHRO.charAt(item))) { // this is the first occurrence of the Sync group
	
		nextB[item]+=interval[item];
		sourceB[item].onended=function(){webAudioPlayBAt(item,nextB[item])};
			
		// This one and all others (sync)
		for (var i = sSYNCHRO.indexOf(sSYNCHRO.charAt(item)); i < iNUMBERBANDS; ++i) {
			if (sSYNCHRO.charAt(item)==sSYNCHRO.charAt(i)) { // belongs to the same group
				  sourceA[i].disconnect(0); // canary crashed with sourceA[i].noteOff(0);
				  sourceA[i] = context.createBufferSource();
				  sourceA[i].buffer = bufferList[i];
				  sourceA[i].playbackRate.value=playbackFactor[i];
				  
				  				  
				  if ((bCALIBRATE==1)&&(i!=movedSlider)&&(movedSlider>-1)) gainNode[i].gain.setTargetAtTime(0,context.currentTime,0);
				  sourceA[i].connect(gainNode[i]);
				  if (bWAVEVISUALIZER) sourceA[i].connect(stemAnalyser[i]);
				  sourceA[i].start(onContextTime);
				  lastPlayedA[i]=onContextTime;
			}
		}
	}
    monitor();}

function webAudioPlayBAt(item,onContextTime){

	// console.log('B@ '+context.currentTime+' for '+onContextTime+' on stem '+item);

	if (item==sSYNCHRO.indexOf(sSYNCHRO.charAt(item))) { // this is the first occurrence of the Sync group.
	
		nextA[item]+=interval[item];
		sourceA[item].onended=function(){webAudioPlayAAt(item,nextA[item])};

	 	// This one and all others (sync)
		for (var i = sSYNCHRO.indexOf(sSYNCHRO.charAt(item)); i < iNUMBERBANDS; ++i) {
			if (sSYNCHRO.charAt(item)==sSYNCHRO.charAt(i)) { // belongs to the same group
				  sourceB[i].disconnect(0); // canary crashed with sourceB[i].noteOff(0);
				  sourceB[i] = context.createBufferSource();
				  sourceB[i].buffer = bufferList[i+iNUMBERBANDS];
				  sourceB[i].playbackRate.value=playbackFactor[i];

				  if ((bCALIBRATE==1)&&(i!=movedSlider)&&(movedSlider>-1)) gainNode[i].gain.setTargetAtTime(0,context.currentTime,0);
				  sourceB[i].connect(gainNode[i]);
		  		  if (bWAVEVISUALIZER) sourceB[i].connect(stemAnalyser[i]);
				  sourceB[i].start(onContextTime);
				  lastPlayedB[i]=onContextTime;
			}
		}
	}
	monitor();}

function playBell() {
    // using simple html5 audio
    if (meditationBell.paused&&!bMUTE) {
        meditationBell.volume=Math.max(0.1,averageSliderLevel);
        meditationBell.play();
    }
}

function stemDrop() {
    var i=Math.floor(Math.random(1)*10);
    console.log("Dropping stem "+i);
    sourceA[i].disconnect(0);
    sourceB[i].disconnect(0);
}

function countIn(index) {
    bDOWNLOADED[index]=1;
    var str="";
    for (var i=0; i<2*iNUMBERBANDS; ++i) if (bDOWNLOADED[i]) str=str+"+"; else str=str+"-";
    if (++launchCounter==iNUMBERBANDS*2) finishedLoading();
    else {     
		var percent=Math.round(launchCounter/20*100);
		var str="<span style='color:#EEE;'>"
					+"•".repeat(launchCounter)
					+"</span>"+percent+"% <span style='color:#777;'>"
					+"•".repeat(Math.max(0,20-launchCounter))
					+"</span>";
		msg("Greasing Sliders "+str);
    }
}


function dlMonitor(index,report,initiator,url) {
    var grandTotal=0;
    var loaded=0;

    // restart if stalled
    var timeOut=10000; // 10s
    if (((Date.now()-iSTARTED[index])>timeOut)&&(iLOADED[index]==report.loaded)) {
        // stalled
        console.log(index+" TIME OUT");
        initiator.abort();
        loadWebAudioSound(url,index);
    } else {
        if (report.lengthComputable) { // myNoise Servers should return Content-Length
            iTOTAL[index]=report.total;
            iLOADED[index]=report.loaded;

            // compute grand total
            for (var i=0; i<2*iNUMBERBANDS; ++i) {
                if (iTOTAL[i]) { grandTotal+=iTOTAL[i]; loaded+=iLOADED[i]; }
            }

            if (grandTotal>serverTotal) serverTotal=grandTotal;
            var loadedMB=Math.floor(loaded/1048576);
            var grandTotalMB=Math.floor(grandTotal/1048576);
            var serverTotalMB=Math.floor(serverTotal/1048576);
            var percent=serverTotal?Math.round(loaded/serverTotal*100):0;

            var str="<span style='color:#EEE;'>"
                +"•".repeat(loadedMB)
                +"</span>"+percent+"% <span style='color:#777;'>"
                +"•".repeat(Math.max(0,grandTotalMB-loadedMB))
                +"</span><span style='color:#333;'>"
                +"•".repeat(Math.max(0,serverTotalMB-grandTotalMB))
                +"</span>";

            document.getElementById("bgimage").style.opacity=percent/100;
            msg("Loading "+str);
        }
    }
}


function monitor() {
    const currentTime=context.currentTime;
    for (let i=0; i<iNUMBERBANDS; ++i) {
        if (interval[i]>0) {
            const elapsed=Math.min(currentTime-lastPlayedA[i],currentTime-lastPlayedB[i]);
            if (elapsed>(interval[i]*1.01)) {
                console.log("Stem "+i+" was lost. Now restarting.");
                lastPlayedA[i]=currentTime;
                lastPlayedB[i]=currentTime;
                restartWebAudio(i);
            }
        }
    }
}

function restartWebAudio(i) {
    sourceA[i].onended=null;
    sourceB[i].onended=null;
    sourceA[i].disconnect(0);
    sourceB[i].disconnect(0);

    sourceA[i]=context.createBufferSource();
    sourceA[i].buffer=bufferList[i];
    sourceA[i].playbackRate.value=playbackFactor[i];
    sourceA[i].connect(gainNode[i]);

    sourceB[i]=context.createBufferSource();
    sourceB[i].buffer=bufferList[i+iNUMBERBANDS];
    sourceB[i].playbackRate.value=playbackFactor[i];
    sourceB[i].connect(gainNode[i]);

    startWebAudio(i);
}

function killWebAudio() { 
    context.close();
    for (let i=0; i<iNUMBERBANDS; ++i) {
        sourceA[i].disconnect(0); sourceB[i].disconnect(0);
        sourceA[i]=null; sourceB[i]=null;
        bufferList[i]=null; bufferList[i+iNUMBERBANDS]=null;
        gainNode[i].disconnect(); 
        gainNode[i]=null; 
    }
    bufferList=null; gainNode=null; sourceA=null; sourceB=null;
}

var bDynamics=1;
function deactivateDynCompressor(){
	if (bDynamics){	
		dynCompressor.disconnect(context.destination);
		mergerNode.disconnect(dynCompressor);
		mergerNode.connect(context.destination);
		msg('[Dynamic Compressor] Bypassed');
		bDynamics=0;
		masterGain.gain.value=fMASTERGAIN;
		}
		else {
			mergerNode.disconnect(context.destination);
			mergerNode.connect(dynCompressor);
			dynCompressor.connect(context.destination);
			msg('[Dynamic Compressor] Activated');
			bDynamics=1;
			masterGain.gain.value=0.5;
		}
}

// INIT

var launchCounter=0;

function init() {

	// initializing jQuery sliders
	for (let i=0; i<iNUMBERBANDS; ++i) {
	  $("#s"+i).slider({
		orientation:"vertical",
		range:"min",
		min:0,
		max:0.99,
		value:0,
		step:0.001,
		animate:"slow",
		slide:function(event,ui){sliderChange(event.target.id);},
		change:function(event,ui){sliderChange(event.target.id);}
	  });
	}
	
	// Redirect if cookies not enabled
	if (!navigator.cookieEnabled) { window.location.href="/showMessage.php?msgID=4"; }
	
	// Check audio file compatibility
	var a=document.createElement("audio");
	if (!!(a.canPlayType&&a.canPlayType('audio/ogg; codecs="vorbis"').replace(/no/,""))){ bSUPPORTOGG=1; serverTotal=totSizeOGG; }
	if (!!(a.canPlayType&&a.canPlayType("audio/mpeg;").replace(/no/,""))){ bSUPPORTMP3=1; }
	
	// Check and initialize Web Audio API
	const AC=window.AudioContext||window.webkitAudioContext;
	if (!AC) {
	  msg('<span style="color:red">ERROR : Web Audio API not found.</span> Switch to a modern browser.');
	  console.log("Cannot initialize the audio engine. Web Audio API required.");
	  return;
	}
	context=new AC();
	console.log("Web Audio [mynoise.world]");
	console.log(navigator.userAgent);
	
	
	tmp=readCookie("LVL");
	if (tmp!=null) {
	  if (tmp==1) fTARGETSLIDERLEVEL=0.33;
	  if (tmp==2) fTARGETSLIDERLEVEL=0.5;
	  if (tmp==3) fTARGETSLIDERLEVEL=0.66;
	}
	
	initTuning();
	msg("... now loading ...");
	assignSources();
	enableButton(["reset","anim","volDown","volUp","mute","fftCanvas","timer","bell","calib","play0","play1","play2","play3","play4","play5","play6","play7","play8","play9"],0);
	disableSliders();
	checkFavGen(); // Highlight Fav icon
	loadAllSounds();
	
	setPreset(0.3,0.3,0.3,0.3,0.3,0.3,0.3,0.3,0.3,0.3);	
	if (!bANIMATIONUSERPROFILESET) {
	  for (let i=0; i<iNUMBERBANDS; ++i) {
		animationProfileHigh[i]=Math.min(currentLevel[i]*1.25,0.99);
		animationProfileLow[i]=currentLevel[i]*0.5;
	  }
	}
	
	// migrateCookies();
	
		
	
	if (/Android/i.test(navigator.userAgent)) {
		MOBILE = 'android';
	} else if (/iPhone|iPad|iPod/i.test(navigator.userAgent)) {
		MOBILE = 'ios';
	}

}

function finishedLoading() {
    masterGain=context.createGain();
    masterGain.gain.value=0.5;

    // Compatibilty with mono files
    for (let i=0; i<bufferList.length; i++) {
        const buf=bufferList[i];
        // if mono buffer, duplicate as stereo
        if (buf&&buf.numberOfChannels===1) {
            const stereo=context.createBuffer(2,buf.length,buf.sampleRate);
            const mono=buf.getChannelData(0);
            stereo.copyToChannel(mono,0);
            stereo.copyToChannel(mono,1);
            bufferList[i]=stereo;
        }
    }

    function makeSource(buffer,rate) {
        const src=context.createBufferSource();
        src.buffer=buffer; // let Web Audio up-mix mono automatically
        src.playbackRate.value=rate;
        // src.loop=true; src.loopStart=...; src.loopEnd=...; // if needed
        return src;
    }

    for (let i=0; i<iNUMBERBANDS; i++) {
        sourceA[i]=makeSource(bufferList[i],playbackFactor[i]);
        gainNode[i]=context.createGain();
        gainNode[i].gain.value=0;
        sourceA[i].connect(gainNode[i]).connect(masterGain);
    }

    for (let i=0; i<iNUMBERBANDS; i++) {
        sourceB[i]=makeSource(bufferList[i+iNUMBERBANDS],playbackFactor[i]);;
        sourceB[i].connect(gainNode[i]).connect(masterGain);
    }
    
    // add mastering compressor
   dynCompressor=new DynamicsCompressorNode(context, {
    	  // working as a limiter
		  threshold: -12, 
		  knee: 6,          
		  ratio: 10,       
		  attack: 0.05,     
		  release: 2      
		});
	dynCompressor.connect(context.destination);
	
    // add the MS coding/decoding part for width
    splitterNode=context.createChannelSplitter(2); // splits stereo into L and R
    mergerNode=context.createChannelMerger(2,2);
    midGain=context.createGain();
    sideGain=context.createGain();
    inverterGain=context.createGain();
    inverterGain.gain.value=-1;
    inverteedSide=context.createGain();
    inverteedSide.gain.value=-1;

    if (bCALIBRATE==0) {
        masterGain.connect(splitterNode);

        // Connect splitterNode to mid and side gain nodes
        splitterNode.connect(midGain,0); // Left channel -> Mid
        splitterNode.connect(midGain,1); // Right channel -> Mid

        // Connect splitterNode to mid and side gain nodes
        splitterNode.connect(sideGain,0); // Left channel -> Side
        splitterNode.connect(inverterGain,1); // Minus Right -> Side-
        inverterGain.connect(sideGain);
        sideGain.connect(inverteedSide);

        // Connect mid and side gain nodes to mergerNode
        midGain.connect(mergerNode,0,0); // Mid -> Left
        midGain.connect(mergerNode,0,1); // Mid -> Right
        sideGain.connect(mergerNode,0,0); // Side -> Left
        inverteedSide.connect(mergerNode,0,1); // Inverted Side -> Right

        // Connect mergerNode to context.destination
        mergerNode.connect(dynCompressor);
    } else masterGain.connect(dynCompressor);

    computeIntervals();

    getCurrentLevelsFromSliders();
    updateDocumentLinks();

    playAllSounds();setAllLevels();
    bFINISHEDLOADING=1;


    // SuperGens - Calling Parent Function
    if (window.parent!=window) window.parent.count();


    // Visualizer - Experimental
    if (bCALIBRATE==0) {
        var analyser=context.createAnalyser();
        analyser.fftSize=32;
        analyser.smoothingTimeConstant=0;
        mergerNode.connect(analyser);
        var fftData=new Float32Array(analyser.frequencyBinCount);
        var c=document.getElementById("fftCanvas");
        var ctx=c.getContext("2d");
        var pos=[0,0,0,0];
        var posOld=[0,0,0,0];
        const WARMUP_MS = 2000;
		const startTs = performance.now();

        function updatefftData() {
            setTimeout(function(){ // throttle requestAnimationFrame
                requestAnimationFrame(updatefftData);
            },100);

            analyser.getFloatFrequencyData(fftData);
            pos[0]=(fftData[0]+75)/2;
            pos[1]=(Math.max(fftData[2],fftData[3])+77)/2;
            pos[2]=(Math.max(fftData[5],fftData[6],fftData[7])+81)/2;
            pos[3]=(Math.max(fftData[9],fftData[10],fftData[11],fftData[12],fftData[13],fftData[14],fftData[15])+89)/2;
            
            let gainReduction = (dynCompressor && typeof dynCompressor.reduction === "number")
			  ? -dynCompressor.reduction
			  : 0;
			  
			const now = performance.now();
			let inWarmup = (now - startTs) < WARMUP_MS;
			if (inWarmup==1) gainReduction=0;

			const distortedGain=3; //db - highlights fully red
	  		let t=gainReduction/distortedGain;
			  if (t<0) t=0;
			  if (t>1) t=1;
			  
			  let r=Math.round(255*t);
			  let g=0;
			  let b=0;
			  let color="rgb(" + r + "," + g + "," + b + ")";

            ctx.beginPath();
            ctx.rect(0,0,c.width,c.height);
            ctx.fillStyle="#eee";
            ctx.fill();
            ctx.closePath();

            var order=[3,1,0,2];

            for (var j=0; j<4; ++j) {
                i=order[j];
                if (pos[i]>posOld[i]) posOld[i]=pos[i]; else posOld[i]--;
                if (posOld[i]<0) posOld[i]=0;
                if (posOld[i]>15) posOld[i]=15;
                ctx.beginPath(); 
                ctx.rect(9+j*5,(c.height-posOld[i]-10),2,posOld[i]); 
                ctx.fillStyle=color; 
                ctx.fill(); 
                ctx.closePath();
            }

            // individual levels
            if (bWAVEVISUALIZER) {
                for (var i=0; i<iNUMBERBANDS; ++i) {
                    stemAnalyser[i].getByteTimeDomainData(samplesArray);
                    var nrg=0;
                    for (var k=0; k<stemAnalyser[i].frequencyBinCount; ++k) {
                        var sample=(samplesArray[k]-128);
                        nrg+=(sample*sample);
                    }
                    nrg=nrg/(128*128);
                    var pixels=13-10*Math.pow(nrg,0.5);
                    pixels=Math.max(pixels,4);
                    document.getElementById("s"+i).lastChild.style.boxShadow="inset 0 0 0 "+pixels+"px rgb(25,27,29)";
                }
            }
        }

        updatefftData();
    }

	// Load GLOBAL parameter settings (if exist)
	
    // iEQ auto start for patrons
    tmp=readCookie("IEQ");
    if (tmp!=null) emphasisEQ(parseFloat(tmp));

    // Stereo Width auto start for patrons
    tmp=readCookie("WID");
    if (tmp!=null) {
        if (tmp==1) setStereoWidth(0);
        if (tmp==2) setStereoWidth(0.5);
        if (tmp==3) setStereoWidth(1);
        if (tmp==4) setStereoWidth(1.8);
    }
    
    // Load URL parameter settings

    var args=getUrlVars();
    loadURLsettings(args);

    // wheel events
    document.getElementById("s0").addEventListener("wheel",function(e){wheeLvl(0,e);});
    document.getElementById("s1").addEventListener("wheel",function(e){wheeLvl(1,e);});
    document.getElementById("s2").addEventListener("wheel",function(e){wheeLvl(2,e);});
    document.getElementById("s3").addEventListener("wheel",function(e){wheeLvl(3,e);});
    document.getElementById("s4").addEventListener("wheel",function(e){wheeLvl(4,e);});
    document.getElementById("s5").addEventListener("wheel",function(e){wheeLvl(5,e);});
    document.getElementById("s6").addEventListener("wheel",function(e){wheeLvl(6,e);});
    document.getElementById("s7").addEventListener("wheel",function(e){wheeLvl(7,e);});
    document.getElementById("s8").addEventListener("wheel",function(e){wheeLvl(8,e);});
    document.getElementById("s9").addEventListener("wheel",function(e){wheeLvl(9,e);});

    $("#bgimage").addClass("animated");
    sliderOpacity();
    
    addMediaSession();
    
     // Suspended Policy by Mobile Browsers and Chrome!

	msg("Hit Play or allow Auto-Play for myNoise.net in your browser settings.");
	if (context.state=="suspended") {
		// bug mobile safari - context can be suspended, and sounds playing!
		// so we need to force suspend even if suspended is detected.
		context.suspend();
		if ("mediaSession" in navigator) navigator.mediaSession.playbackState="paused";
		bSUSPENDED=1;
		enableButton(["mute"],1);
		$("#mute").click(resumeContext);
		console.log("This browser doesn't trust myNoise and has suspended the audio context.");
	} else {
		$("#mute").click(toggleMute);
	}
	
	 // Enable Buttons
    if (!bSUSPENDED) nowPlaying();

    // Timer Gens
    if (bSTARTMUTED==1) forceMute(1);
}


function waveVisualizer() {
    bWAVEVISUALIZER=1-bWAVEVISUALIZER;
    if (bWAVEVISUALIZER) {
        msg("Visualizer ON [V]");
        for (let i=0; i<iNUMBERBANDS; ++i) {
            if (!stemAnalyser[i]) {
                stemAnalyser[i]=context.createAnalyser();
                stemAnalyser[i].fftSize=512;
                if (i==0) samplesArray=new Uint8Array(stemAnalyser[i].frequencyBinCount); // create once
            }
            sourceA[i].connect(stemAnalyser[i]);
            sourceB[i].connect(stemAnalyser[i]);
        }
    } else {
        msg("Visualizer OFF [V]");
        for (let i=0; i<iNUMBERBANDS; ++i) {
            document.getElementById("s"+i).lastChild.style.boxShadow="inset 0 0 0 4px rgb(25,27,29)";
        }
        for (let i=0; i<iNUMBERBANDS; ++i) {
            sourceA[i].disconnect(stemAnalyser[i]);
            sourceB[i].disconnect(stemAnalyser[i]);
        }
    }
}

function wheeLvl(i,e) {
    e.preventDefault();
    let offset=-e.deltaY/1000;
    currentLevel[i]=Math.max(0,Math.min(0.99,currentLevel[i]+offset));
    savedLevel[i]=Math.max(0,Math.min(0.99,currentLevel[i]+offset));
    randomCounter=0; // anim
    $("#s"+i).slider("value",currentLevel[i]);
}

function pad(num) {
    let s="000"+num;
    return s.substr(s.length-2);
}

function sliderChange(movedSliderName) {
    if (bFINISHEDLOADING==1) {
        movedSlider=movedSliderName.substring(1,2);
        if (bCALIBRATE==1) {
            for (let i=0; i<iNUMBERBANDS; ++i) {
                if (i!=movedSlider) {
                    gainNode[i].gain.setTargetAtTime(0,context.currentTime,0);
                }
            }
            msg("2. Move each slider so that its associated sound becomes just audible to you.");
        } else {
            if (bANIMATE==0) msg("");
        }
        currentLevel[movedSlider]=$("#s"+movedSlider).slider("value");
        gainNode[movedSlider].gain.setTargetAtTime(Math.pow(currentLevel[movedSlider],3),context.currentTime,fAUDIOFADETIME);
    }
    updateDocumentLinks();
    if (!bMEDITATIONSESSION) computeAverageSliderLevel();
    if (movedSliderName==lastSlider) {
        var db=Math.round(26*Math.log(currentLevel[movedSlider]));
        msg(db+" dBFS");
    } else lastSlider=movedSliderName;
    sliderOpacity();
    learnAssignSlider(movedSliderName);
}


function sliderOpacity() {
    if ((bANIMATE==0)&&(bDISABLE==0)) {
        for (let i=0; i<iNUMBERBANDS; ++i) {
            if (currentLevel[i]==0) {
                document.getElementById("s"+i).style.opacity=0.3;
            } else {
                document.getElementById("s"+i).style.opacity=1;
            }
        }
    }
}

// Link Management

function buildAnimationParams(){
  var seg="&a="+iAnimationFactor+"&am="+iAnimationMode;
  if (bANIMATIONUSERPROFILESET){
    seg+="&apl="+packVector(animationProfileLow)+"&aph="+packVector(animationProfileHigh);
  }
  if (bANIMATE) seg+="&astart=1";
  return seg;
}

function updateDocumentLinks(){

	// --- What do links save ---
	// l=  packed slider levels (packVector(currentLevel))
	// m=  magic generator id (when applicable)
	// submission= community generator id (when applicable)
	// a=  animation speed (iAnimationFactor)
	// am= animation mode (iAnimationMode)
	// apl=/aph= animation profiles (when user profile set)
	// astart=1 auto-start animation flag
	// mt=1 mute flag
	// title= custom title (if present in #titleName)
	// d=  detune (pitch shift)
	// w=  stereo width (if != 1)
	// c=  context: 1=clone/share, 2=order, 4=testimonial
	// (URLbell / URLtimer, when defined globally, are appended as-is)

	// --- Debounce guard ---
  	// Use a property on the function itself to store the timer
	  clearTimeout(updateDocumentLinks._timer);
	  updateDocumentLinks._timer = setTimeout(() => {
  
   // --- The originam code starts here ---


  // Base pieces (inline assignments for simple cases)
  var strippedDocumentURL="/NoiseMachines/spaceshipNoiseGenerator.php";
  URLlevels="l="+packVector(currentLevel);
  URLanimate=buildAnimationParams();

  // Magic/community generator segment (PHP injects exactly as before)
  URLmagic="";
  
  URLdetune=(detune?"&d="+detune:"");
  URLwidth=(typeof fSTEREOWIDTH!=="undefined" && fSTEREOWIDTH!=1)?"&w="+fSTEREOWIDTH:"";
  URLmute=(bMUTE?"&mt=1":"");
  URLtitle=(function(){
  			var el=document.getElementById("titleName");
  			return el?"&title="+encodeURI(el.textContent):"";
  			})();
  			
  			
  var qConcatenated=URLlevels+URLanimate+URLmagic+URLdetune+URLwidth+URLmute+URLbell+URLtimer+URLtitle;

  // Update anchors 
  $("#customURL0").attr("href", strippedDocumentURL+"?"+qConcatenated);
  $("#customURL1").attr("href", strippedDocumentURL+"?"+qConcatenated+"&c=4");
  $("#customURL2").attr("href", strippedDocumentURL+"?"+qConcatenated+"&c=2");

  // Expose cloneURL + cookieURL 
  cloneURL=strippedDocumentURL+"?"+qConcatenated+"&c=1";
  cookieURL=qConcatenated.substring(2); // drop "l="
  
  // The QR Code thing
  const concatenatedCodes = sourceFileA.map(url => {
	  // Extract folder name and the first digit after it
	  const match = url.match(/Data\/([^/]+)\/(\d)/);
	  if (!match) return '';
	  const code = match[1];
	  const digit = match[2];
	  return `${code}${digit}`;
		}).filter(Boolean).join('~');
   appShareURL="https://mynoi.se/shared.php?"+URLlevels+"&m="+concatenatedCodes+URLdetune+URLtitle;

   // --- End of your original logic ---

  }, 500); // 0.5 second debounce delay
  
}

function openQrPopup() {

// if we're on mobile, just open the link directly
  if (MOBILE) {
    window.open(appShareURL, '_blank');
    return;
  }
  
  const popup = document.getElementById('qrPopup');
  const qrContainer = document.getElementById('qrPopupCode');
  popup.style.display = 'flex';
  
  console.log(appShareURL);

  // Generate or update QR
  if (!openQrPopup._qr) {
    openQrPopup._qr = new QRCode(qrContainer, {
      text: appShareURL,
      width: 200,
      height: 200,
      correctLevel: QRCode.CorrectLevel.M
    });
  } else {
    openQrPopup._qr.clear();
    openQrPopup._qr.makeCode(appShareURL);
  }

  // Any click closes it
  popup.addEventListener('click', () => {
    popup.style.display = 'none';
  }, { once: true });
}

function getLink() {
    return cloneURL.slice(15);
}

function cloneIt() {
    window.open(cloneURL,"_blank","toolbar=yes,scrollbars=yes,width=500,height=430");
    document.location.href="/noiseMachines.php";
}

function print() {
    console.log(currentLevel.join(","));
}

function getCurrentLevelsFromSliders() {
    for (let i=0; i<iNUMBERBANDS; ++i) {
        currentLevel[i]=$("#s"+i).slider("value");
    }
}

function setCurrentLevelsToSliders() {
    for (let i=0; i<iNUMBERBANDS; ++i) {
        $("#s"+i).slider("value",currentLevel[i]);
    }
}

function setSlidersToZero() {
    for (let i=0; i<iNUMBERBANDS; ++i) {
        $("#s"+i).slider("value",0);
    }
}

function setAllLevels() {
    for (let i=0; i<iNUMBERBANDS; ++i) {
        gainNode[i].gain.setTargetAtTime(Math.pow(currentLevel[i],3),context.currentTime,fAUDIOFADETIME);
    }
}

function fadeOut(out, duration_s) {
  let now=context.currentTime; // current audio time in seconds
  let target = 0;
  if (out==0) {
  	if (bEQ==1) target=gainForEQ;
  	else target=fMASTERGAIN;
  }

  // If we are fading OUT, stop the animation timer
  if (bANIMATE==1 && out==1) clearTimeout(modulationTimeout);
  
  masterGain.gain.cancelScheduledValues(now);
  masterGain.gain.setValueAtTime(masterGain.gain.value, now);
  masterGain.gain.linearRampToValueAtTime(target, now + duration_s);

	  // Schedule one timeout for after the fade finishes
	  clearTimeout(fadeTimeOut);
	  fadeTimeOut = setTimeout(function() {
		  if (out==1) {
				// We have faded OUT: pause audio context
				if (context.state !== 'suspended') {
					context.suspend();
					console.log("Audio Engine: suspended (saving CPU)");
					}
				if (navigator.mediaSession) {navigator.mediaSession.playbackState = 'paused';}
		  	} 
		  	else {
				if (navigator.mediaSession) {navigator.mediaSession.playbackState = 'playing';}
				// Resume animation after fade-in completes
				if (bANIMATE == 1) {modulationRandom();}
		  	}
	},  duration_s*1000);
}


function initTuning() {
    for (var i = 0; i < iNUMBERBANDS; ++i) playbackFactor[i] = 1;
    var args = getUrlVars();
    if (args["d"] !== undefined) {
        detune = args["d"];
        detune = detune.replace(/(?!^-)[^0-9.]/g, "");   // keep "-" at start, digits, and "." to avoid XSS zapping
    }
    computePlaybackFactorsFromDetune();
    // TO DO Update the UI showing C# as default
}

function tune(factor, bRelative = false) {

	if (bRelative) {
 		let currentFactor = Math.pow(2, detune / 12);
 		factor = currentFactor * factor;
    }
    
    detune=Math.round(Math.log2(factor)*12*1000)/1000;
    updatePlaybackRate();
    updateDocumentLinks();
    msg("Now playing at "+Math.round(factor*100)/100+"x original tape speed.");

    // Highlight the corresponding key in the Tape Speed section
    // Normalize the factor for comparison
    var rounded=Math.round(factor*1000000);
    document.querySelectorAll(".transposeKey").forEach(function(el) {
        // Extract number from onclick (e.g., tune(0.943874);)
        var match=el.getAttribute("onclick").match(/tune\(([\d.]+)\)/);
        if (match) {
            var elFactor=Math.round(parseFloat(match[1])*1000000);
            if (elFactor===rounded) {
                el.classList.add("highlight");
                el.classList.remove("actionlink");
            } else {
                el.classList.remove("highlight");
                el.classList.add("actionlink");
            }
        }
    });
}


function transposeDetune(amount,limitMin,limitMax) {
	 // Ensure detune is a string to analyze its form
    let strDetune=detune.toString();
    if (strDetune.length<4) {
        // Global detune case
        let detuneValue = parseFloat(detune); // Ensure numeric
        let newValue=detuneValue+amount;
        if (newValue>=limitMin&&newValue<=limitMax) {
            detune=newValue;
            let value=Math.round(Math.pow(2,detune/12)*100)/100;
            if (detune===0) msg("Master tape is now spinning at original speed.");
            else msg("Master tape playing at "+value+"x speed.");
        } else {
            msg("Tape Speed : not further speed change allowed.");
        }
    } else if (strDetune.length===20) {
        // Concatenated detune case
        let newDetune="";
        for (let i=0; i<20; i+=2) {
            let value=parseInt(strDetune.substring(i,i+2),10);
            let newValue=value+amount;
            if (newValue>=50+limitMin&&newValue<=50+limitMax) {
                value=newValue;
            } else {
                msg("Tape Speed Error : Out of range");
                return;
            }
            newDetune+=String(value).padStart(2,"0");
        }
        detune=newDetune;
        msg(transposeString(detune));
    }
    updatePlaybackRate();
    updateDocumentLinks();
}

function transposeString(detuneString) {
  let result = "";
  for (let i=0; i<20; i+=2) {
    let value=parseInt(detuneString.substring(i, i+2), 10);
    let transposed=value-50;
    let direction=transposed>=0 ? "&uarr;" : "&darr;";
    let magnitude=Math.abs(transposed);
    result+=direction+magnitude+" ";
  }
  return result;
}

function tuneDown(dec) { transposeDetune(-dec, -48, 36);}
function tuneUp(inc) { transposeDetune(inc, -48, 36); }
function octDown() { transposeDetune(-12, -48, 36); }
function octUp() { transposeDetune(12, -48, 36); }

function mixedTune(keyScale=null) {
  // aabbcc...jj where xx = 50+/-detune
  var strSettings="";
  for (var i=0; i<iNUMBERBANDS; ++i) {
    var thisSetting;
    if (Array.isArray(keyScale)&&keyScale.length>0) {
      // Choose a random value from the provided key scale
      thisSetting=keyScale[Math.floor(Math.random()*keyScale.length)];
    } else {
      // Default behavior: Random semitone shift between ±7
      thisSetting=Math.round(Math.random()*7)*(Math.random()<0.5?-1:1);
    }
    var value=50+thisSetting; // Apply transposition
    strSettings+=String(value).padStart(2, "0"); // Ensure two-digit formatting
  }

  detune=strSettings;
  updateDocumentLinks();
  updatePlaybackRate();
  msg(transposeString(detune));
}

function computePlaybackFactorsFromDetune() {
  const isScalar=detune<999;
  for (let i=0; i<iNUMBERBANDS; ++i) {
    if (isScalar) {
      playbackFactor[i]=Math.pow(2, detune/12);
    } else {
      const step=parseInt(detune.toString().substring(i*2, i*2+2))-50;
      playbackFactor[i]=Math.pow(2, step/12);
    }
  }
}

function updatePlaybackRate() {
  computePlaybackFactorsFromDetune();
  computeIntervals();
  for (let i=0; i<iNUMBERBANDS; ++i) {
    restartWebAudio(i);
  }
}

function setAnimationSpeed(value) {
  if (typeof value==="undefined") {
    if (iAnimationFactor==1) iAnimationFactor=0.5;
    else if (iAnimationFactor==0.5) iAnimationFactor=0.25;
    else if (iAnimationFactor==0.25) iAnimationFactor=0.125;
    else if (iAnimationFactor==0.125) iAnimationFactor=2;
    else if (iAnimationFactor==2) iAnimationFactor=4;
    else if (iAnimationFactor==4) iAnimationFactor=8;
    else if (iAnimationFactor==8) iAnimationFactor=1;
  } else {
    iAnimationFactor=value;
  }

  customLinkAssign("asdiv8", "actionlink", "&div;8");
  customLinkAssign("asdiv4", "actionlink", "&div;4");
  customLinkAssign("asdiv2", "actionlink", "&div;2");
  customLinkAssign("asmult8", "actionlink", "x8");
  customLinkAssign("asmult4", "actionlink", "x4");
  customLinkAssign("asmult2", "actionlink", "x2");
  customLinkAssign("asnormal", "actionlink", "Normal");

  if (iAnimationFactor==1) {
    msg("Animation Speed : Normal");
    customLinkAssign("asnormal", "highlight", "Normal");
  }
  if (iAnimationFactor==0.125) {
    msg("Animation Speed : Slowest");
    customLinkAssign("asdiv8", "highlight", "&div;8");
  }
  if (iAnimationFactor==0.25) {
    msg("Animation Speed : Slower");
    customLinkAssign("asdiv4", "highlight", "&div;4");
  }
  if (iAnimationFactor==0.5) {
    msg("Animation Speed : Slow");
    customLinkAssign("asdiv2", "highlight", "&div;2");
  }
  if (iAnimationFactor==2) {
    msg("Animation Speed : Fast");
    customLinkAssign("asmult2", "highlight", "x2");
  }
  if (iAnimationFactor==4) {
    msg("Animation Speed : Faster");
    customLinkAssign("asmult4", "highlight", "x4");
  }
  if (iAnimationFactor==8) {
    msg("Animation Speed : Fastest");
    customLinkAssign("asmult8", "highlight", "x8");
  }

  updateDocumentLinks();
}

function setAnimationMode(value){

 	if(typeof value === "undefined") {
		if (iAnimationMode=="s") iAnimationMode="h";
		else if (iAnimationMode=="h") iAnimationMode="i";
		else if (iAnimationMode=="i") iAnimationMode="d";
		else if (iAnimationMode=="d") iAnimationMode="t";
		else if (iAnimationMode=="t") iAnimationMode="q";
		else if (iAnimationMode=="q") iAnimationMode="s";
		
	}
	else iAnimationMode=value;
	
	customLinkAssign('amSoft','actionlink','Soft');
	customLinkAssign('amHard','actionlink','Hard');
	customLinkAssign('amIsolated','actionlink','Solo');
	customLinkAssign('amDuo','actionlink','Duo');
	customLinkAssign('amTrio','actionlink','Trio');
	customLinkAssign('amQuad','actionlink','Quad');

	if (iAnimationMode==="s"){
		msg("Animation Mode : Soft (default)");
		customLinkAssign('amSoft','highlight','Soft');
		}
	if (iAnimationMode==="h"){
		msg("Animation Mode : Hard");
		customLinkAssign('amHard','highlight','Hard');
		}
	if (iAnimationMode==="i"){
		msg("Animation Mode : Solo");
		customLinkAssign('amIsolated','highlight','Solo');
		}
	if (iAnimationMode==="d"){
		msg("Animation Mode : Duo");
		customLinkAssign('amDuo','highlight','Duo');
		}
	if (iAnimationMode==="t"){
		msg("Animation Mode : Trio");
		customLinkAssign('amTrio','highlight','Trio');
		}
	if (iAnimationMode==="q"){
		msg("Animation Mode : Quad");
		customLinkAssign('amQuad','highlight','Quad');
		}
	updateDocumentLinks();

}

function setAnimationProfile(type) {
    bANIMATIONUSERPROFILESET = 1;

    if (type == "lo") {
        for (var i = 0; i < iNUMBERBANDS; ++i) {
            animationProfileLow[i] = currentLevel[i];
        }
        msg("Current slider profile was saved as LOW slider animation bound");
    }
    if (type == "hi") {
        for (var i = 0; i < iNUMBERBANDS; ++i) {
            animationProfileHigh[i] = currentLevel[i];
        }
        msg("Current slider profile was saved as HIGH slider animation bound");
    }

    updateDocumentLinks();
}

function loadAnimationProfile(type) {
    if (type == "lo") {
        currentLevel = animationProfileLow.slice(0);
        msg("LOW slider animation profile");
    }
    if (type == "hi") {
        currentLevel = animationProfileHigh.slice(0);
        msg("HIGH slider animation profile");
    }
    setCurrentLevelsToSliders();
}


function setPreset(l0,l1,l2,l3,l4,l5,l6,l7,l8,l9,text){
		if (bMUTE==1) toggleMute();

		if (bCALIBRATE==0) {
			// level normalization

			var power=8; // supposedly 3 but too loud when only few sliders are active
	
			var l0lin,l1lin,l2lin,l3lin,l4lin,l5lin,l6lin,l7lin,l8lin,l9lin;
			l0lin=Math.pow(l0,power);l1lin=Math.pow(l1,power);l2lin=Math.pow(l2,power);l3lin=Math.pow(l3,power);l4lin=Math.pow(l4,power);
			l5lin=Math.pow(l5,power);l6lin=Math.pow(l6,power);l7lin=Math.pow(l7,power);l8lin=Math.pow(l8,power);l9lin=Math.pow(l9,power);
		
			var totLevellin=l0lin+l1lin+l2lin+l3lin+l4lin+l5lin+l6lin+l7lin+l8lin+l9lin;
	
			if (totLevellin>0) {
				// O=bottom, 1=max linear scale
				var ltargettotlin=Math.pow(fTARGETSLIDERLEVEL,power)*10;
				var mult=Math.pow(ltargettotlin,1/power)/Math.pow(totLevellin,1/power);
				l0=Math.min(l0*mult,0.99);l1=Math.min(l1*mult,0.99);l2=Math.min(l2*mult,0.99);l3=Math.min(l3*mult,0.99);l4=Math.min(l4*mult,0.99);
				l5=Math.min(l5*mult,0.99);l6=Math.min(l6*mult,0.99);l7=Math.min(l7*mult,0.99);l8=Math.min(l8*mult,0.99);l9=Math.min(l9*mult,0.99);
			}
		}
		
		currentLevel[0]=l0;currentLevel[1]=l1;currentLevel[2]=l2;currentLevel[3]=l3;currentLevel[4]=l4;
		currentLevel[5]=l5;currentLevel[6]=l6;currentLevel[7]=l7;currentLevel[8]=l8;currentLevel[9]=l9;
		saveRandomExchange();
		
		if (bANIMATE==0) {
		  setCurrentLevelsToSliders();
		  if(typeof(text)==='undefined') msg("");else msg(text);
		}
		
		customLinkAssign('emphasis','actionlink','Apply Calibration',emphasis);
}

function resetSliders(){
	setPreset(0.3,0.3,0.3,0.3,0.3,0.3,0.3,0.3,0.3,0.3,"Back to Default");}

function randomSettings() {
    var r=new Array();
    for (var i=0; i<iNUMBERBANDS; ++i) {
        if (Math.random()>0.3) r[i]=Math.random();
        else r[i]=0;
    }
    setPreset(r[0],r[1],r[2],r[3],r[4],r[5],r[6],r[7],r[8],r[9],'Random');
}


// Apply Calibration to current sliders

function emphasis() {
    var tag="CAL";
    var calLevel;
    var totalLevelBefore=0;
    var totalLevelAfter=0;
    var userData={};
    var cookieName='uSET_'+uIDS;
    if (cookieName=='uSET_') cookieName='uSET_unlogged';
    var tmp=readCookie(cookieName);
    if (tmp!=null) userData=JSON.parse(tmp);
    if (userData[tag]!=null) {
        for (var i=0; i<iNUMBERBANDS; ++i) {
            calLevel=userData[tag].substring(2*i,2*i+2)/100;
            totalLevelBefore+=currentLevel[i];
            currentLevel[i]=currentLevel[i]*(calLevel/0.3);
            totalLevelAfter+=currentLevel[i];
        }
        for (var i=0; i<iNUMBERBANDS; ++i) {
            currentLevel[i]=currentLevel[i]*totalLevelBefore/totalLevelAfter;
        }
        emphasisEQ(0);
        setCurrentLevelsToSliders();
        msg("Calibration curve applied to the sliders.");
    } else {
        msg("ERROR: no calibration found. Please <a href='/calibration.php'>calibrate</a> first.");
    }
    customLinkAssign('tosliders','white','> Applied to Sliders','');
    customLinkAssign('full','lowlight','Full','');
    customLinkAssign('balanced','lowlight','Balanced','');
    customLinkAssign('none','lowlight','None','');
}


function emphasisEQ(factor) {
    var tag="CAL";
    var calLevel;
    var userData={};
    var cookieName="uSET_"+uIDS;
    if (cookieName=="uSET_") cookieName="uSET_unlogged";
    var tmp=readCookie(cookieName);
    if (tmp!=null) userData=JSON.parse(tmp);

    if (userData[tag]!=null) {
        masterGain.gain.value=0;
        var dB=new Array();
        var totdB=0;
        var mindB=999999;

        if (!bEQ) {
            // setup and re-wiring
            var freqs=[20,60,125,250,500,1000,2000,4000,8000,17000];
            for (var i=0; i<iNUMBERBANDS; ++i) {
                eqNode[i]=context.createBiquadFilter();
                eqNode[i].type="peaking";
                eqNode[i].frequency.value=freqs[i];
                eqNode[i].Q.value=0.25;
                eqNode[i].gain.value=0;
            }
            for (var i=0; i<iNUMBERBANDS; ++i) {
                gainNode[i].connect(eqNode[0]);
                gainNode[i].disconnect(masterGain);
            }
            for (var i=0; i<iNUMBERBANDS-1; ++i) {
                eqNode[i].connect(eqNode[i+1]);
            }
            eqNode[9].connect(masterGain);
            bEQ=1;
        }


        // get cal curve in dB
        for (var i=0; i<iNUMBERBANDS; ++i) {
            calLevel=userData[tag].substring(2*i,2*i+2)/100;
            if (calLevel>0) dB[i]=Math.round(26*Math.log(calLevel));
            else dB[i]=0;
            totdB+=dB[i];
            if (dB[i]<mindB) mindB=dB[i];
        }

        // apply gain
        for (var i=0; i<iNUMBERBANDS; ++i) {
            eqNode[i].gain.setTargetAtTime(factor*(dB[i]-mindB),context.currentTime,0.01);
        }

		gainForEQ=1/Math.pow(10,factor*((totdB/10)-mindB)/10)*0.6;
        masterGain.gain.setTargetAtTime(gainForEQ*0.5,context.currentTime,0.1);

        customLinkAssign("full","actionlink","Full");
        customLinkAssign("balanced","actionlink","Balanced");
        customLinkAssign("none","actionlink","None");

        switch (factor) {
            case 1:
                customLinkAssign("full","white","Full");
                msg("Full calibration - best for headphones compensation");
                break;
            case 0.5:
                customLinkAssign("balanced","white","Balanced");
                msg("Balanced calibration - best for hearing compensation");
                break;
            case 0:
                customLinkAssign("none","white","None");
                msg("iEQ is now bypassed - no compensation applied");
                break;
        }
    } else {
        msg("ERROR: no calibration found. Please <a href='/calibration.php'>calibrate</a> first.");
    }
}

function setStereoWidth(widthFactor) {
    fSTEREOWIDTH=widthFactor;
    updateDocumentLinks();

    // Set the gain values for mid and side
    midGain.gain.setTargetAtTime(1,context.currentTime,0.2);
    sideGain.gain.setTargetAtTime(1*widthFactor,context.currentTime,0.2);

    // Assign default link labels
    customLinkAssign("smono","actionlink","Mono");
    customLinkAssign("snarrow","actionlink","Narrow");
    customLinkAssign("snormal","actionlink","Normal");
    customLinkAssign("swide","actionlink","Wide");

    // Display appropriate message and highlight the active link
    if (widthFactor===0) {
        msg("Stereo width set to Mono");
        customLinkAssign("smono","white","Mono");
    } else if (widthFactor===0.5) {
        msg("Stereo width set to Narrow");
        customLinkAssign("snarrow","white","Narrow");
    } else if (widthFactor===1) {
        msg("Stereo width set to original Stereo (Headphones)");
        customLinkAssign("snormal","white","Normal");
    } else if (widthFactor===1.8) {
        msg("Stereo width set to Wide (Speakers)");
        customLinkAssign("swide","white","Wide");
    } else {
        msg("Stereo width set to "+Math.round(widthFactor*100)+"%");
    }
}
// Experimental

	async function setDiffusion() {
		const convolver = context.createConvolver();
		const impulseResponseBuffer = await loadImpulseResponse("/Audio/diffusion.wav");
		convolver.buffer = impulseResponseBuffer;
		// Create a Gain12Node to boost the convolver signal by 12 dB
		const gain12Node = context.createGain();
		gain12Node.gain.value = Math.pow(10, 12/ 20);  // Convert 12 dB to linear gain
		masterGain.disconnect(splitterNode);
		masterGain.connect(convolver);
		convolver.connect(gain12Node);  // Connect convolver to gain node
		gain12Node.connect(context.destination);  // Connect gain node to destination
	}
	
	async function loadImpulseResponse(url) {
		const response = await fetch(url);
		const arrayBuffer = await response.arrayBuffer();
		return await context.decodeAudioData(arrayBuffer);
	}



function customLinkAssign(id,classname,innerhtml,onclickfuntion) {
    if (document.getElementById(id)) {
        document.getElementById(id).className=classname;
        document.getElementById(id).innerHTML=innerhtml;
        if (arguments.length==4) document.getElementById(id).onclick=onclickfuntion;
    }
}

function packVector(v) {
  let str=
    pad(Math.round(v[0]*100))+
    pad(Math.round(v[1]*100))+
    pad(Math.round(v[2]*100))+
    pad(Math.round(v[3]*100))+
    pad(Math.round(v[4]*100))+
    pad(Math.round(v[5]*100))+
    pad(Math.round(v[6]*100))+
    pad(Math.round(v[7]*100))+
    pad(Math.round(v[8]*100))+
    pad(Math.round(v[9]*100));
  return str;
}

function saveCurrentLevelsToCookie(tag) {
    // omit tag for personal curve
    if (tag===undefined) tag="CAL";
    // load Cookie
    var userData={};
    var cookieName='uSET_'+uIDS;
    if (cookieName=='uSET_') cookieName='uSET_unlogged';
    var tmp=JSON.parse(readCookie(cookieName));
    if (tmp!=null) userData=tmp;
    // Save Associative Array
    userData[tag]=cookieURL;
    // Save Assicative Array
    var days=36500;
    createCookie(cookieName,JSON.stringify(userData),days);
    if (tag!="CAL") msg("All settings now saved as a browser cookie...");
}

function loadCurrentLevelsFromCookieAndSetSliders(tag) {
    if (tag===undefined) tag="CAL";
    var userData={};
    var cookieName='uSET_'+uIDS;
    if (cookieName=='uSET_') cookieName='uSET_unlogged';
    var tmp=JSON.parse(readCookie(cookieName));
    if (tmp!=null) userData=tmp;
    if (userData[tag]!=null) {
        var args=getUrlVars('?l='+userData[tag]);
        loadURLsettings(args);
        initTuning();
    	updatePlaybackRate();
        if (tag=="CAL") msg("Your Personal Curve");
        else msg("Your Custom Settings for this noise");
    } else {
        if (tag=="CAL") msg("ERROR: no data found. Please  <a href='/calibration.php'>calibrate</a> (donor, log in first).");
        else msg("ERROR: no user setting found, save one first.");
    }

}

function restartWebAudio(i) {
    let fadeTime = 0.05; // 50ms fade
    let now = context.currentTime;

    // Save current gain values BEFORE fade out
    let originalGainA = Math.pow(currentLevel[i],3)
    let originalGainB = Math.pow(currentLevel[i],3)

    // Fade out
    gainNode[i].gain.cancelScheduledValues(now);
    gainNode[i].gain.setValueAtTime(gainNode[i].gain.value, now);
    gainNode[i].gain.linearRampToValueAtTime(0, now + fadeTime);

    // Delay restart until fade-out completes
    setTimeout(() => {
        // Disconnect and clean up
        sourceA[i].onended = null;
        sourceB[i].onended = null;
        try { sourceA[i].disconnect(); } catch (e) {}
        try { sourceB[i].disconnect(); } catch (e) {}

        // Recreate sources
        sourceA[i] = context.createBufferSource();
        sourceA[i].buffer = bufferList[i];
        sourceA[i].playbackRate.value = playbackFactor[i];
        sourceA[i].connect(gainNode[i]);

        sourceB[i] = context.createBufferSource();
        sourceB[i].buffer = bufferList[i + iNUMBERBANDS];
        sourceB[i].playbackRate.value = playbackFactor[i];
        sourceB[i].connect(gainNode[i]);

        // Start playback
        startWebAudio(i);

        // Fade back to original gain (instead of hardcoded 1)
        let resumeTime = context.currentTime;
        gainNode[i].gain.setValueAtTime(0, resumeTime);
        gainNode[i].gain.linearRampToValueAtTime(originalGainA, resumeTime + fadeTime);

    }, fadeTime * 1000);
}



function loadURLsettings(args){
    if (args['l']!==undefined) {
        let code=args['l'].replace(/\D/g,''); // XSS zapping all non digits
        for (let i=0; i<iNUMBERBANDS; ++i) {currentLevel[i]=code.substring(2*i,2*i+2)/100;}
        setCurrentLevelsToSliders();
    }
    if (args['apl']!==undefined) {
        let code=args['apl'].replace(/\D/g,''); // XSS zapping all non digits
        for (let i=0; i<iNUMBERBANDS; ++i) {animationProfileLow[i]=code.substring(2*i,2*i+2)/100;}
        bANIMATIONUSERPROFILESET=1;
    }
    if (args['aph']!==undefined) {
        let code=args['aph'].replace(/\D/g,''); // XSS zapping all non digits
        for (let i=0; i<iNUMBERBANDS; ++i) {animationProfileHigh[i]=code.substring(2*i,2*i+2)/100;}
        bANIMATIONUSERPROFILESET=1;
    }
    if (args['a']!==undefined) {
        setAnimationSpeed(args['a']);
    }
    if (args['am']!==undefined) {
        setAnimationMode(args['am']);
    }
    if (args['astart']!==undefined) {
        if (args['astart']==1) { startModulation(); }
    }
    if (args['d']!==undefined) {
		detune=args['d'];
    }
    if (args['tm']!==undefined) {
        let minutes=parseInt(args['tm'],10);
        if (!isNaN(minutes)) {
            setTimer(minutes);
            activateButton(["timer"],1);
        }
    }
    if (args['bl']!==undefined) {
        let minutes=decodeURIComponent(args['bl']);
        if ((minutes>0)||(typeof minutes==="string"&&minutes.includes(":"))) {
            setMeditationBell(minutes);
            activateButton(["bell"],1);
        }
    }
    if (args['mt']!==undefined) {
        let mute=parseInt(args['mt'],10);
        if (mute===1) forceMute(1);
    }
    if (args['w']!==undefined) {
        let width=parseFloat(args['w']);
        if (!isNaN(width)) setStereoWidth(width);
    }
    if (bSUSPENDED) resumeContext();
}

function disableSliders() {
    for (let i=0; i<iNUMBERBANDS; ++i) disableSlider(i);
    bDISABLE=1;
}

function enableSliders() {
    for (let i=0; i<iNUMBERBANDS; ++i) enableSlider(i);
    bDISABLE=0;
}

function disableSlider(i) {
    let $el=$("#s"+i);
    $el.addClass("disabled");
    $el.slider("option","disabled",true);
}

function enableSlider(i) {
    let $el=$("#s"+i);
    $el.removeClass("disabled");
    $el.slider("option","disabled",false);
}

function toggleCalibration() {
    bCALIBRATE=!bCALIBRATE;
    if (bCALIBRATE==1) {
        enableSliders();
        movedSlider=-99;
        $("#caliBtn").html("3.&nbsp; Save Your Personal Curve");
        console.log('###1');
    } else {
        saveCurrentLevelsToCookie();
        setAllLevels();
        disableSliders();
        $("#caliBtn").html("Done! (Click to recalibrate)");
        console.log('###2');
    }
}

function toggleModulation(bNoMsg) {
    bANIMATE=!bANIMATE;
    if (bANIMATE==1) {
        if (!bANIMATIONUSERPROFILESET) {
            let tmp=0;
            for (let i=0; i<iNUMBERBANDS; ++i) {
                tmp+=currentLevel[i];
                animationProfileHigh[i]=Math.min(currentLevel[i]*1.25,0.99);
                animationProfileLow[i]=currentLevel[i]*0.5;
            }
            if (tmp==0) {
                // we have a problem, animation will start with all-zero min max.
                for (let i=0; i<iNUMBERBANDS; ++i) animationProfileHigh[i]=fTARGETSLIDERLEVEL*1.25;
            }
        }

        savedLevel=currentLevel.slice(0); // copy values, not ref!
        savedCurrentLevel=currentLevel.slice(0); // copy values, not ref!
        nzSliderIndex=[];
        mmMin=1;mmMax=0;
        for (let i=0; i<iNUMBERBANDS; ++i) {
            if (savedLevel[i]>0) {
                if (savedLevel[i]<mmMin) mmMin=savedLevel[i];
                if (savedLevel[i]>mmMax) mmMax=savedLevel[i];
                nzSliderIndex.push(i);
            }
        }
        disableSliders();
        updateButtons();
        modulationRandom();
    } else {
        // currentLevel=savedLevel.slice(0); // copy values, not ref!
        clearTimeout(modulationTimeout);
        enableSliders();
        updateButtons();
        setCurrentLevelsToSliders();
        randomCounter=0;
    }
    if (bNoMsg!=1) {
        if (bANIMATE==1) msg("Sliders are on the move...");
        else msg("Slider animation has been stopped");
    }
}

function stopModulation() {
    if (bANIMATE==1) {
        toggleModulation(1);
        randomCounter=0;
    }
}

function startModulation() {
    if (bANIMATE==0) {
        toggleModulation(1);
    }
}

function modulationRandom(){
	function getRandomIndices(count,eligibleIndices) {
	  // clamp to avoid impossible requests
	  count = Math.min(count, eligibleIndices.length);
	  // make a shallow copy so we can shuffle without mutating the original
	  const copy = eligibleIndices.slice();
	  // Fisher–Yates shuffle up to the needed count
	  for (let i = copy.length - 1; i > copy.length - 1 - count; i--) {
		const j = Math.floor(Math.random() * (i + 1));
		[copy[i], copy[j]] = [copy[j], copy[i]];
	  }
	  // take the last `count` elements (shuffled ones)
	  return copy.slice(-count);
	}

    iCurrentAnimationSpeed=iINITIALANIMATIONSPEED/iAnimationFactor;
    let nCycle=10; // number of steps between snapshots

    if (randomCounter==0) {   // time to generate a new random state from the saved curve
        let ranSlider8=-1;
        let count8=0;
        let max8=0;

        if (iAnimationMode==8) {
            for (let i=0; i<iNUMBERBANDS; ++i) {
                if (savedLevel[i]==0) {count8++;}
                else if (savedLevel[i]>max8) max8=savedLevel[i];
            }
            if (count8<2) { msg('This animation mode requires a couple of sliders set to zero');}
            else {
                while (ranSlider8<0){
                    let ran8=Math.floor(Math.random()*10);
                    if (savedLevel[ran8]==0) ranSlider8=ran8;
                }
            }
            max8=Math.min(max8*1.15,0.99);
        }

        savedCurrentLevel=currentLevel.slice(0);  // save where we come from, copy values, not ref!

        for (let i=0; i<iNUMBERBANDS; ++i) {
            let smin,smax;
            if (iAnimationMode==1) {smin=0.5;smax=1.25;}
            if (iAnimationMode==2) {smin=0.8;smax=1.1;}
            if (iAnimationMode==3) {smin=0;smax=1.5;}
            let ran=(smax-smin)*Math.random()+smin;
            if (iAnimationMode<4)  {randomLevel[i]=ran*savedLevel[i];}
            if (iAnimationMode==4) {if (savedLevel[i]>0) randomLevel[i]=Math.random()*(mmMax-mmMin)+mmMin; else randomLevel[i]=0;}
            if (iAnimationMode==5) {if (Math.random()>0.6) randomLevel[i]=0; else randomLevel[i]=savedLevel[i];}
            if (iAnimationMode==6) {randomLevel[i]=savedLevel[Math.floor(Math.random()*10)];}
            if (iAnimationMode==7) {if (savedLevel[i]>0) randomLevel[i]=savedLevel[nzSliderIndex[Math.floor(Math.random()*nzSliderIndex.length)]]; else randomLevel[i]=0;}
            if (iAnimationMode==8) {
                if (i==ranSlider8) randomLevel[i]=max8;
                else randomLevel[i]=savedLevel[i];
            }
            if (randomLevel[i]>0.99) randomLevel[i]=0.99;
        }

        // new animations modes
        if (iAnimationMode=="s") {
            for (let i=0; i<iNUMBERBANDS; ++i) {randomLevel[i]=animationProfileLow[i]+Math.random()*(animationProfileHigh[i]-animationProfileLow[i]);}
        }
        if (iAnimationMode=="h") {
            for (let i=0; i<iNUMBERBANDS; ++i) {
                if (Math.random()<0.5) randomLevel[i]=animationProfileHigh[i];
                else randomLevel[i]=animationProfileLow[i];
            }
        }
        if (["i", "d", "t", "q"].includes(iAnimationMode)){
            let eligibleIndices=[];
            for (let i=0; i<iNUMBERBANDS; ++i) {
                if (animationProfileLow[i]!==animationProfileHigh[i]) {
                    eligibleIndices.push(i);
                }
            }
            switch (iAnimationMode) {
                case 'i':
                    animatedIndices=getRandomIndices(1,eligibleIndices);
                    break;
                case 'd':
                    if (!Array.isArray(animatedIndices) || animatedIndices.length !== 2) {
						// initialize
						animatedIndices = getRandomIndices(2, eligibleIndices);
					} else {
						// change one of the two
						const newIndices = animatedIndices.slice();
						const available = eligibleIndices.filter(x => !animatedIndices.includes(x));
			
						if (available.length > 0) {
							const pos = Math.floor(Math.random() * 2);
							const replacement = available[Math.floor(Math.random() * available.length)];
							newIndices[pos] = replacement;
						}
						animatedIndices = newIndices;
					}
					break;
                case 't':
                    if (!Array.isArray(animatedIndices) || animatedIndices.length !== 3) {
						// initialize
						animatedIndices = getRandomIndices(3, eligibleIndices);
					} else {
						// change one of the three
						const newIndices = animatedIndices.slice();
						const available = eligibleIndices.filter(x => !animatedIndices.includes(x));
			
						if (available.length > 0) {
							const pos = Math.floor(Math.random() * 3);
							const replacement = available[Math.floor(Math.random() * available.length)];
							newIndices[pos] = replacement;
						}
						animatedIndices = newIndices;
					}
					break;
				case 'q':
               if (!Array.isArray(animatedIndices) || animatedIndices.length !== 4) {
						// initialize
						animatedIndices = getRandomIndices(4, eligibleIndices);
					} else {
						// change one of the three
						const newIndices = animatedIndices.slice();
						const available = eligibleIndices.filter(x => !animatedIndices.includes(x));
			
						if (available.length > 0) {
							const pos = Math.floor(Math.random() * 4);
							const replacement = available[Math.floor(Math.random() * available.length)];
							newIndices[pos] = replacement;
						}
						animatedIndices = newIndices;
					}
					break;
                default:
            }

            for (let i=0; i<iNUMBERBANDS; ++i) {
                if (animatedIndices.includes(i)) {
                    randomLevel[i]=Math.max(animationProfileLow[i],animationProfileHigh[i]);
                } else {
                    randomLevel[i]=Math.min(animationProfileLow[i],animationProfileHigh[i]);
                }
            }
        }
    }

    for (let i=0; i<iNUMBERBANDS; ++i) {
        if (selSliders[i]) {currentLevel[i]=savedCurrentLevel[i]+randomCounter*(randomLevel[i]-savedCurrentLevel[i])/nCycle;}
    }
    setCurrentLevelsToSliders();
    if (++randomCounter==(nCycle+1)) randomCounter=0;
    clearTimeout(modulationTimeout);
    modulationTimeout=setTimeout(function(){modulationRandom();},iCurrentAnimationSpeed*1000/nCycle);
}

///////////

function saveRandomExchange(){
    savedLevel=currentLevel.slice(0);
    randomLevel=currentLevel.slice(0);
    msg("Animation data has been updated!");
    randomCounter=0;
}

function toggleMute() {
    iFadeState=0;
    bMUTE=!bMUTE;
    if (bMUTE==1) {
        if (iTimer==0) fadeOut(1,30);
        else fadeOut(1,0.5);
        if (iMTimer>0) setMeditationBell(0);
        updateButtons();
        if (iTimer==0) msg("It's time to... slowly fade out... (and sleep)");
        else msg("Press Play to resume");
    } else {
        if (iTimer==0) fadeOut(0,15);
        else fadeOut(0,1);
        updateButtons();
        if (iTimer==0) msg("It's time to... slowly fade in... (and wake up)");
        else msg("Now Playing...");
        resumeContext();
    }
    if (iTimer==0) iTimer=-1;
    updateDocumentLinks();
}

function forceMute(bTurnOn) {
    if (bTurnOn) {
        bMUTEsaved=bMUTE;
        if (!bMUTE) toggleMute();
    } else {
        if (!bMUTEsaved&&bMUTE) toggleMute();
    }
    bMUTEFORCED=bTurnOn;
}

function startMuted(){bSTARTMUTED=1;}

function returnMute(){return bMUTE;}

function updateButtons(){
    if (bMUTE==1) {
        // document.getElementById("mute").src = "/Pix/icon_play.png";
        document.getElementById("mute").style.display="flex";
        document.getElementById("fftCanvas").style.display="none";
        enableButton(["reset","anim","volDown","volUp","calib","bell"],0);
        disableSliders();
    } else {
        // document.getElementById("mute").src = "/Pix/icon_pause.png";
        document.getElementById("mute").style.display="none";
        document.getElementById("fftCanvas").style.display="block";
        enableButton(["reset","anim","volDown","volUp","calib","bell"],1);
        if (bANIMATE==1) {
            activateButton(["anim"],1);
        } else {
            enableButton(["reset"],1);
            activateButton(["anim"],0);
            enableSliders();        }
    }
}

function setTimer(time) {
    if ((typeof time==="undefined")||(isNaN(time))) {
        var elapsed=((new Date).getTime()-epoch);
        iTimer=Math.max(0,iTimer-elapsed/60000+2);
        if (iTimer<1) {iTimer=1;msg("Timer set to 1 minute");activateButton(["timer"],1);}
        else if (iTimer<5) {iTimer=5;msg("Timer set to 5 minutes");}
        else if (iTimer<10) {iTimer=10;msg("Timer set to 10 minutes");}
        else if (iTimer<15) {iTimer=15;msg("Timer set to 15 minutes");}
        else if (iTimer<20) {iTimer=20;msg("Timer set to 20 minutes");}
        else if (iTimer<25) {iTimer=25;msg("Pomodoro time! (25 minutes) Keyboard Shortcut: o");}
        else if (iTimer<30) {iTimer=30;msg("Timer set to 30 minutes");}
        else if (iTimer<60) {iTimer=60;msg("Timer set to 1 hour");}
        else if (iTimer<120) {iTimer=120;msg("Timer set to 2 hours");}
        else if (iTimer<240) {iTimer=240;msg("Timer set to 4 hours");}
        else if (iTimer<480) {iTimer=480;msg("Timer set to 8 hours");}
        else {iTimer=-1;msg("Timer is disabled");activateButton(["timer"],0);}
    } else {
        if (time==0) {iTimer=0;updateTimer();}
        else {
            iTimer=time;
            msg("Timer set to "+time+" min");
        }
    }
    URLtimer='&tm='+iTimer;
    if (iTimer==-1) URLtimer='';
    updateDocumentLinks();

    if (document.getElementById('timerText')!==null) {
        if (iTimer>0) document.getElementById('timerText').value=iTimer;
        else document.getElementById('timerText').value="";
        document.getElementById('timerText').blur();
    }

    epoch=(new Date).getTime(); //ms
    clearTimeout(timerTimeout);
    timerTimeout=setTimeout(function(){updateTimer();},10000);
}

function updateTimer() {
    if (iTimer<0) return;

    var elapsed=((new Date).getTime()-epoch);
    var remaining=iTimer*60-elapsed/1000; //s

    if (remaining<=0) {
        // disable all interface
        iTimer=0;
        activateButton(["timer"],0);
        toggleMute();
        if (document.getElementById('timerText')!==null) document.getElementById('timerText').value="";
    } else {
        if (document.getElementById('timerText')!==null) document.getElementById('timerText').value=Math.ceil(remaining/60);
        clearTimeout(timerTimeout);
        timerTimeout=setTimeout(function(){updateTimer();},10000);
    }
}

function setMeditationBell(time) {
    playBell();
    clearTimeout(meditationInterval);clearTimeout(meditationInterval2);

    if (typeof time==="undefined") {
        if (iMTimer<1) {iMTimer=1;time=1;activateButton(["bell"],1);}
        else if (iMTimer<5) {iMTimer=5;time=5;}
        else if (iMTimer<10) {iMTimer=10;time=10;}
        else if (iMTimer<15) {iMTimer=15;time=15;}
        else if (iMTimer<20) {iMTimer=20;time=20;}
        else if (iMTimer<25) {iMTimer=25;time=25;}
        else if (iMTimer<30) {iMTimer=30;time=30;}
        else if (iMTimer<60) {iMTimer=60;time=60;}
        else if (iMTimer<99999) {iMTimer=99999;time="5:60"}
        else {iMTimer=-1;time=-1;activateButton(["bell"],0);}
    }
    // time is now defined
    if (isNaN(time)) { // not numeric (random setting such as nn:mm)
        time=time.replace("?",":");
        time=time.replace("-",":");
        var parts=time.split(":");
        if (parts.length==2) {
            if (isNaN(parts[0])) return; if (isNaN(parts[1])) return;
            var minTime=Math.min(parts[0],parts[1]);
            var maxTime=Math.max(parts[0],parts[1]);
            var nextBell=Math.round(minTime+Math.random()*(maxTime-minTime));
            meditationInterval=setTimeout(function(){setMeditationBell(time)},nextBell*60000);
            msg("Random Bells from "+minTime+" to "+maxTime+" min");
            if (document.getElementById('bellText')!==null) document.getElementById('bellText').value="R";
        } else {
            parts=time.split("+");
            if (parts.length==2) {
                if (isNaN(parts[0])) return; if (isNaN(parts[1])) return;
                var firstTime=parts[0];
                var secondTime=parts[1];
                var totalTime=parseFloat(firstTime)+parseFloat(secondTime);
                meditationInterval=setTimeout(function(){playBell()},firstTime*60000);
                meditationInterval2=setTimeout(function(){setMeditationBell(time)},totalTime*60000);
                msg("Dual Session Bell : "+firstTime+"•"+secondTime+"•"+firstTime+"•"+secondTime+" ... min");
                if (document.getElementById('bellText')!==null) document.getElementById('bellText').value="D";
            }
        }
    } else { // numeric
        iMTimer=time;
        if (iMTimer>0) {
            if (iMTimer==1) msg("Meditation Bell every minute");
            else if (iMTimer==25) msg("Pomodoro Bell (25 minutes) Shortcut: Shift+o");
            else if (iMTimer==60) msg("Meditation Bell every hour");
            else msg("Meditation Bell every "+time+" min");

            if (document.getElementById('bellText')!==null) document.getElementById('bellText').value=iMTimer;
        } else {
            msg("Meditation Bell now disabled"); activateButton(["bell"],0)
            if (document.getElementById('bellText')!==null) document.getElementById('bellText').value="";
        }
        if (iMTimer>0) meditationInterval=setInterval(function(){playBell();},iMTimer*60000);
    }

    URLbell='&bl='+encodeURIComponent(time);
    if (time==-1) URLbell='';
    updateDocumentLinks();

    if (document.getElementById('bellText')!==null) document.getElementById('bellText').blur();
}

function collectNZ() {
    var userData={};
    var cookieName='collectBuffer';
    var tmp=readCookie(cookieName);
    var collected=0;
    if (tmp!=null) userData=JSON.parse(tmp);
    else {
        userData['codes']=[];
        userData['levels']=[];
        userData['detunes']=[];
        userData['pass']=0;
    }
    for (var i=0; i<iNUMBERBANDS; ++i) {
        if (currentLevel[i]>0) {
            var urlParsed=sourceFileA[i].substring(sourceFileA[i].indexOf('Data/')).split("/");
            userData['codes'].push(urlParsed[1]+urlParsed[2].substring(0,1));
            userData['levels'].push(Math.round(currentLevel[i]*100));
            userData['detunes'].push(Math.round(Math.log2(playbackFactor[i])*12));
            collected=1;
        }
    }

    if (collected) userData['pass']+=1;

    // trimming
    while (userData['codes'].length>10) {
        userData['codes'].shift();
        userData['levels'].shift();
    }
    console.log("Custom Stack : ");
    console.log(userData);
    // saving
    var days=1;
    createCookie(cookieName,JSON.stringify(userData),days);
    msg("[Custom] Non-zero sliders have been collected ["+userData['codes'].length+"/10]");
}


function clearStack() {
	var userData={};
	var cookieName='collectBuffer';
	var tmp=readCookie(cookieName);
	userData['codes']=[];
	userData['levels']=[];
	userData['detunes']=[];
	userData['pass']=0;
	var days=1;
	createCookie(cookieName,JSON.stringify(userData),days);
	msg("[Custom] Stack is now cleared [0/10]");
}

function customGenLaunch() {
    var url;
    var userData={};
    var cookieName='collectBuffer';
    var tmp=readCookie(cookieName);
    if (tmp!=null) userData=JSON.parse(tmp);
    else {
        userData['codes']=[];
        userData['levels']=[];
        userData['detunes']=[];
        userData['pass']=0;
    }
    if (userData['codes'].length<10) msg("[ERROR] Collect 10 individual sliders first! ("+userData['codes'].length+" collected)");
    else {
        // sort stack
        var userDataSorted={};
        userDataSorted['codes']=[];
        userDataSorted['levels']=[];
        userDataSorted['detunes']=[];
        for (var i=0; i<iNUMBERBANDS; ++i) {
            for (var j=0; j<userData['codes'].length; ++j) {
                if (userData['codes'][j].substr(-1)==i) {
                    userDataSorted['codes'].push(userData['codes'][j]);
                    userDataSorted['levels'].push(userData['levels'][j]);
                    userDataSorted['detunes'].push(userData['detunes'][j]);
                }
            }
        }
        // generate url
        url="https://mynoise.net/NoiseMachines/custom.php?l="
        for (var i=0; i<iNUMBERBANDS; ++i) {
            url+=String(userDataSorted['levels'][i]).padStart(2,'0');
        }

        url+='00&m=';
        for (var i=0; i<iNUMBERBANDS; ++i) url+=userDataSorted['codes'][i]+'~';
        url=url.substring(0,url.length-1);
        // add detune string
        var bDetuned=0;
        for (var i=0; i<iNUMBERBANDS; ++i) if (userDataSorted['detunes'][i]!=0) bDetuned=1;
        if (bDetuned) {
            url+="&d=";
            for (var i=0; i<iNUMBERBANDS; ++i) {
                url+=String(50+userDataSorted['detunes'][i]).padStart(2,'0');
            }
        }

        var title=window.prompt("[Custom] Your custom generator is almost ready! We are just a short title away...","A Short Title");
        if (title==null||title=="") {
            // User cancelled
        } else {
            original='';
            if (userData['pass']>1) original='&orig=1';
            url+=original+'&title='+encodeURIComponent(titleCase(title.trim()));
            window.open(url,"_self");
        }
    }
}

function titleCase(str) {
    var splitStr=str.toLowerCase().split(' ');
    for (var i=0; i<splitStr.length; i++) splitStr[i]=splitStr[i].charAt(0).toUpperCase()+splitStr[i].substring(1);
    return splitStr.join(' ');
}

function help() {
    var myWindow=window.open("/NoiseMachines/help.php","myNoise Help","width=480,height=800");
}

function selectedSlidersAdd(s) {

        if (selSliders[10]==3) {  // Audio Fade
            fAUDIOFADETIME=s;
            msg("[Audio Fade] Confirmed "+fAUDIOFADETIME+"s");
            selSliders[10]=1;
        }
        if (selSliders[10]==4) {  // Random Select
            selSliders=[0,0,0,0,0,0,0,0,0,0,1];
            selectedSlidersRandom(s);
            var weight=0;
            for (var i=0; i<iNUMBERBANDS; ++i) {weight+=selSliders[i];}
            selectedSlidersHighlight(0.45-0.015*weight);
        }
        if (selSliders[10]<2) { // selSliders[10]=currently adding stems flags
            if (selSliders[10]==0) selSliders=[1,1,1,1,1,1,1,1,1,1,1];
            selSliders[s]=1-selSliders[s];
            selectedSlidersDraw();
        }

}

function selectedSlidersReset() {
    var weight=0;
    for (var i=0; i<iNUMBERBANDS; ++i) {weight+=selSliders[i];}
    if (weight>1) selSliders=[0,0,0,0,0,0,0,0,0,0,1];
    else selSliders=[1,1,1,1,1,1,1,1,1,1,1];
    selectedSlidersDraw();
}

function selectedSlidersRandom(proba) {
    for (var i=0; i<iNUMBERBANDS; ++i) {
        if (Math.random()<(proba/10)) selSliders[i]=1;
        else selSliders[i]=0;
    }
    selectedSlidersDraw();
}

function selectedSlidersHighlight(value) {
    for (var i=0; i<iNUMBERBANDS; ++i) {
        if (selSliders[i]) $("#s"+i).slider("value",value);
        else $("#s"+i).slider("value",0);
    }
    selectedSlidersDraw();
}

function selectedSlidersFunction(type) {
    switch(type) {
        case 0: // invert
            for (let i=0; i<iNUMBERBANDS; ++i) selSliders[i]=1-selSliders[i];
            break;
        case 1: // below-average select
            let sum=0;
            for (let i=0; i<iNUMBERBANDS; ++i) sum+=currentLevel[i];
            sum/=10;
            for (let i=0; i<iNUMBERBANDS; ++i) {
                if (currentLevel[i]<sum) selSliders[i]=1;
                else selSliders[i]=0;
            }
            break;
    }
    selSliders[10]=0;
    selectedSlidersDraw();
}

function selectedSlidersDraw() {
    for (let i=0; i<iNUMBERBANDS; ++i) {
        let $slider=$("#s"+i);
        if (selSliders[i]) {
            $slider.removeClass("ui-slider-vertical_lowlight");
            $slider.addClass("ui-slider-vertical");
        } else {
            $slider.removeClass("ui-slider-vertical");
            $slider.addClass("ui-slider-vertical_lowlight");
        }
    }
}

function selectedSlidersVolUp(offset) {
    for (let i=0; i<iNUMBERBANDS; ++i) {
        if (selSliders[i]) {
            currentLevel[i]=Math.min(0.99,currentLevel[i]+offset);
            savedLevel[i]=Math.min(0.99,savedLevel[i]+offset);
            randomCounter=0;  // anim
            $("#s"+i).slider("value",currentLevel[i]);
        }
    }
}

function selectedSlidersVolDown(offset) {
    for (let i=0; i<iNUMBERBANDS; ++i) {
        if (selSliders[i]) {
            currentLevel[i]=Math.max(0,currentLevel[i]-offset);
            savedLevel[i]=Math.max(0,savedLevel[i]-offset);
            randomCounter=0;  // anim
            $("#s"+i).slider("value",currentLevel[i]);
        }
    }
}

function selectedSlidersVolUpDown(offset) {
    var weight=0;
    for (var i=0; i<iNUMBERBANDS; ++i) {weight+=selSliders[i];}
    if (weight==0) {selectedSlidersRandom(5);for (var i=0; i<iNUMBERBANDS; ++i) {weight+=selSliders[i];}}
    if (weight==10) selectedSlidersVolUp(offset);
    else {
        var offsetUp=offset*5/weight;
        var offsetDown=offset*5/(10-weight);
        for (var i=0; i<iNUMBERBANDS; ++i) {
            if (selSliders[i]) {
                var value=Math.min($("#s"+i).slider("option","value")+offsetUp,1);
                $("#s"+i).slider("value",value);
            } else {
                var value=Math.max($("#s"+i).slider("option","value")-offsetDown,0);
                $("#s"+i).slider("value",value);
            }
        }
    }
}

function slidersUp(){ // mutiplicative to avoid stuck at zero
    if (bMUTE==1) toggleMute();
    for (var i=0; i<iNUMBERBANDS; ++i) {
        currentLevel[i]=Math.min(0.99,currentLevel[i]*fLevelMultiplier);
        savedLevel[i]=Math.min(0.99,savedLevel[i]*fLevelMultiplier); randomCounter=0;  //anim
        if (bANIMATE==1) {
            animationProfileLow[i]=Math.min(0.99,animationProfileLow[i]*fLevelMultiplier);
            animationProfileHigh[i]=Math.min(0.99,animationProfileHigh[i]*fLevelMultiplier);
        }
        $("#s"+i).slider("value",currentLevel[i]);
    }
    computeAverageSliderLevel();
}

function slidersDown(){ // mutiplicative to avoid stuck at zero
    if (bMUTE==1) toggleMute();
    for (var i=0; i<iNUMBERBANDS; ++i) {
        currentLevel[i]=currentLevel[i]/fLevelMultiplier;
        savedLevel[i]=savedLevel[i]/fLevelMultiplier; randomCounter=0; //anim
        if (bANIMATE==1) {
            animationProfileLow[i]=animationProfileLow[i]/fLevelMultiplier;
            animationProfileHigh[i]=animationProfileHigh[i]/fLevelMultiplier;
        }
        $("#s"+i).slider("value",currentLevel[i]);
    }
    computeAverageSliderLevel();
}


// ***** managing button long presses
function volDownMouseDown() {
    isLongPress=false;
    longPressTimer=setTimeout(startLongPressDown,300);
}

function volDownMouseUp() {
    clearTimeout(longPressTimer);
    if (!isLongPress) {
        slidersDown();
    } else {
        clearInterval(longPressTimer);
        fLevelMultiplier=1.1;
    }
}

function volUpMouseDown() {
    isLongPress=false;
    longPressTimer=setTimeout(startLongPressUp,300);
}

function volUpMouseUp() {
    clearTimeout(longPressTimer);
    if (!isLongPress) {
        slidersUp();
    } else {
        clearInterval(longPressTimer);
        fLevelMultiplier=1.1;
    }
}

function startLongPressUp() {
    isLongPress=true;
    fLevelMultiplier=1.01;
    longPressTimer=setInterval(slidersUp,100);
}

function startLongPressDown() {
    isLongPress=true;
    fLevelMultiplier=1.01;
    longPressTimer=setInterval(slidersDown,100);
}


// ***** managing slider dragging onto the volume up and down buttons

let buttonsDisabled=false;
let reenableTimeout=null;

function onSliderMouseDown(e) {
    disableVolumeButtons();
}

function onSliderMouseMove(e) {
    if (buttonsDisabled) {
        resetReenableTimer();
    }
}

function disableVolumeButtons() {
    if (!buttonsDisabled) {
        buttonsDisabled=true;
        const buttons=document.querySelectorAll('#volUp, #volDown');
        buttons.forEach(btn=>{
            btn.style.pointerEvents='none';
        });
    }

    resetReenableTimer();
}

function resetReenableTimer() {
    // Cancel previous timer if it exists
    if (reenableTimeout) {
        clearTimeout(reenableTimeout);
    }

    // Start new timer
    reenableTimeout=setTimeout(()=>{
        const buttons=document.querySelectorAll('#volUp, #volDown');
        buttons.forEach(btn=>{
            btn.style.pointerEvents='auto';
        });
        buttonsDisabled=false;
        reenableTimeout=null; // clear the reference
    },1000);
}

// ***** 


function computeAverageSliderLevel(){
    var max=0;
    var sum=0;
    for (var i=0; i<iNUMBERBANDS; ++i) {
        sum+=currentLevel[i];
        if (currentLevel[i]>max) max=currentLevel[i];
    }
    averageSliderLevel=(max*10+sum)/20;
    if (bMEDITATIONSESSION) {for (var i=0; i<7; ++i) if (voiceover[i]) voiceover[i].volume=averageSliderLevel/2;}
    meditationBell.volume=Math.max(0.1,averageSliderLevel/2);
}

function selectedSlidersZero(type){
    if (type>0) {
        for (var i=0; i<iNUMBERBANDS; ++i) {if (selSliders[i]==1) $("#s"+i).slider("value",0);}
    } else {
        for (var i=0; i<iNUMBERBANDS; ++i) {if (selSliders[i]==0) $("#s"+i).slider("value",0);}
    }
}

function selectedSlidersShift(dir){
    var tmp;
    if (dir>0) {
        tmp=selSliders[9];
        for (var i=iNUMBERBANDS-1; i>0; --i) selSliders[i]=selSliders[i-1];
        selSliders[0]=tmp;
    } else {
        tmp=selSliders[0];
        for (var i=0; i<iNUMBERBANDS-1; ++i) selSliders[i]=selSliders[i+1];
        selSliders[9]=tmp;
    }
    selectedSlidersDraw();
}

function startMeditationRoom(){

	if (bSUSPENDED) resumeContext();
	setTimer(0);
	
	forceMute(0);

	bMEDITATIONSESSION=1-bMEDITATIONSESSION;
	
	if (bMEDITATIONSESSION) {
	
	
	var element=document.getElementById("bgimage");
	element.classList.remove("animated");
	element.style.backgroundImage="url(/Pix/bgMeditationRoom2x.jpg)";
	void element.offsetWidth; // trick to trigger re-animation
  	element.classList.add("animated");
	disableSliders();
		enableButton(["reset","anim","mute","fftCanvas","timer","bell","calib","play0","play1","play2","play3","play4","play5","play6","play7","play8","play9"],0);
		fAUDIOFADETIME=3;
		msg("Controls have been disabled. Relax and close your eyes");
		
		allContents=document.getElementById("description").innerHTML;
		$( ".nestedSection" ).hide();
		$( "#description" ).show();
		
		document.getElementById("description").innerHTML="<div class='contentText'><h1>Welcome to the Meditation Room</h1><p>Find a quiet place where you will not be interrupted for the next 10 minutes. Meditations cannot be paused. If you got interrupted, you are invited to <span class='actionlink' onclick='startMeditationRoom()'>&rarr; Leave The Meditation Room</span>, and come back later again when you will be fully available. I will still be here, waiting for you ;-)</p><blockquote>The myNoise meditation room uses prompts from a pool of different meditation scripts, so your experience will be different between visits.</blockquote><p><img src='/Pix/stephane.png' width='100px'></p><p class='lowlight'><em>This function is still in beta. Do not hesitate to contact me - stephane at mynoise dot net - to leave feedback about your experience, and share suggestions for improvements.</em></p> </div>";
	
		setPreset(0,0,0,0,0,0,0,0,0,0,"Meditation Room");
		//playBell();
		
		for (var i = 0; i<7; ++i) { 
			if (!voiceover[i]){voiceover[i]=new Audio('/Audio/MeditationRoom/'+i+'_'+Math.floor(1+Math.random()*5)+fileExt);voiceover[i].preload='auto';}			
			voiceover[i].volume=averageSliderLevel;
		}
				
		var s=[0,1,2,3,4,5,6,7,8,9];
		s=s.sort((a, b) => 0.5 - Math.random());
		var p=new Array();
		var k=0;
		
		var maxDur=[7,14,7,16,65,17,19];
		var startOffset=8;

		sto[k++]=setTimeout(function(){voiceover[0].play();},startOffset*1000);
		sto[k++]=setTimeout(function(){voiceover[1].play();},(startOffset+maxDur[0]+3)*1000);
		sto[k++]=setTimeout(function(){voiceover[2].play();},(startOffset+maxDur[0]+maxDur[1]+6)*1000);
		sto[k++]=setTimeout(function(){voiceover[3].play();},(startOffset+maxDur[0]+maxDur[1]+maxDur[2]+9)*1000);
		sto[k++]=setTimeout(function(){voiceover[4].play();},(startOffset+maxDur[0]+maxDur[1]+maxDur[2]+maxDur[3]+12)*1000);
		sto[k++]=setTimeout(function(){voiceover[5].play();},(540-maxDur[5]-maxDur[6]-6)*1000);
		sto[k++]=setTimeout(function(){voiceover[6].play();},(540)*1000);
		
		
		sto[k++]=setTimeout(function(){fAUDIOFADETIME=10; 
				p=[0,0,0,0,0,0,0,0,0,0];
				p[s[0]]=averageSliderLevel; 
				setPreset(p[0],p[1],p[2],p[3],p[4],p[5],p[6],p[7],p[8],p[9],"")},(startOffset+maxDur[0]+3)*1000);
		sto[k++]=setTimeout(function(){fAUDIOFADETIME=60; 
				p[s[1]]=averageSliderLevel; p[s[2]]=averageSliderLevel;p[s[3]]=averageSliderLevel; 
				setPreset(p[0],p[1],p[2],p[3],p[4],p[5],p[6],p[7],p[8],p[9],"")},(startOffset+maxDur[0]+maxDur[1]+maxDur[2]+6)*1000);
		sto[k++]=setTimeout(function(){fAUDIOFADETIME=60; 
				p=[0,0,0,0,0,0,0,0,0,0];
				p[s[4]]=averageSliderLevel; p[s[5]]=averageSliderLevel;
				setPreset(p[0],p[1],p[2],p[3],p[4],p[5],p[6],p[7],p[8],p[9],"")},3*60000);
		sto[k++]=setTimeout(function(){fAUDIOFADETIME=60; 
				p=[0,0,0,0,0,0,0,0,0,0];
				p[s[6]]=averageSliderLevel; p[s[7]]=averageSliderLevel; 
				setPreset(p[0],p[1],p[2],p[3],p[4],p[5],p[6],p[7],p[8],p[9],"")},5*60000);
		sto[k++]=setTimeout(function(){fAUDIOFADETIME=60; 
				p=[0,0,0,0,0,0,0,0,0,0];
				p[s[8]]=averageSliderLevel; p[s[9]]=averageSliderLevel; 
				setPreset(p[0],p[1],p[2],p[3],p[4],p[5],p[6],p[7],p[8],p[9],"")},7*60000);		
		sto[k++]=setTimeout(function(){fAUDIOFADETIME=60; 
				setPreset(0,0,0,0,0,0,0,0,0,0,"")},9*60000);
		sto[k++]=setTimeout(function(){fAUDIOFADETIME=0.1;startMeditationRoom();},10*60000);
				
	} else {
		msg("You left the meditation room.");
		$('#bgimage').removeClass("animated");
		$('#bgimage').css("background-image", "url(/Data/SPACESHIP/bg.jpg)");
		$('#bgimage').addClass("animated");
		document.getElementById("description").innerHTML=allContents;
		$( "#description" ).hide();
		$( ".nestedSection" ).show();
		for (var i = 0; i<sto.length; ++i) {clearTimeout(sto[i]);};
		for (var i = 0; i<7; ++i) {if (!voiceover[i].paused) {voiceover[i].pause();voiceover[i].currentTime=0;}}
		fAUDIOFADETIME=0.1;
		enableSliders();
		enableButton(["reset","anim","mute","fftCanvas","timer","bell","calib","play0","play1","play2","play3","play4","play5","play6","play7","play8","play9"],1);
	}


}

function experimentalAudioFadeMode() { msg("[Audio Fade] Enter time (0..9)"); selSliders[10]=3;}
function ranNSliders() { msg("[Pick Sliders] Enter Proba (0..9)"); selSliders[10]=4;}

// Keypresses

// Non English keyboards. To be completed.
Mousetrap.addKeycodes({80:'p',32:'space',65:'a',83:'s',68:'d',82:'r',75:'k',74:'j',84:'t',76:'l',72:'h',73:'i'});

Mousetrap.bind('p', function() { toggleMute(); });
Mousetrap.bind('space', function(e) {
    if (e.preventDefault) {
        e.preventDefault();
    } else {
        // internet explorer
        e.returnValue = false;
    }
    toggleMute();
});
Mousetrap.bind('esc', function() { window.location='/noiseMachines.php' });
Mousetrap.bind('a', function() { toggleModulation(); });
Mousetrap.bind('s', function() { setAnimationSpeed(); });
Mousetrap.bind('d', function() { setAnimationMode(); });
Mousetrap.bind('r', function() { $("#reset").click(); });
Mousetrap.bind('k', function() { slidersUp(); });
Mousetrap.bind('j', function() { slidersDown(); });
Mousetrap.bind('t', function() { $("#timer").click(); });
Mousetrap.bind('shift+t', function() { setTimer(0); activateButton(["timer"],0);$("#mute").click(); msg("Timer Reset");});
Mousetrap.bind('l', function() { $("#bell").click(); });
Mousetrap.bind('h', function() { help(); });
Mousetrap.bind('v', function() { waveVisualizer(); });
Mousetrap.bind('o', function() { if (bMUTE) setTimer(5); else setTimer(25); activateButton(["timer"],1);msg("Pomodoro timer set!");});
Mousetrap.bind('shift+o', function()  { setMeditationBell('25+5');activateButton(["bell"],1);msg("Pomodoro bell : 25•5•25•5•... min ");});
Mousetrap.bind('w', function() { setPreset(0.18,0.21,0.24,0.27,0.3,0.34,0.38,0.42,0.46,0.5,"White"); });
Mousetrap.bind('n', function() { setPreset(0.3,0.3,0.3,0.3,0.3,0.3,0.3,0.3,0.3,0.3,"Pink"); });
Mousetrap.bind('b', function() { setPreset(0.5,0.46,0.42,0.38,0.34,0.3,0.27,0.24,0.21,0.18,"Brown"); });
Mousetrap.bind('z', function() { setPreset(0,0,0,0,0,0,0,0,0,0,"Zeroed"); });
Mousetrap.bind('0', function() { selectedSlidersAdd(0);});
Mousetrap.bind('1', function() { selectedSlidersAdd(1);});
Mousetrap.bind('2', function() { selectedSlidersAdd(2);});
Mousetrap.bind('3', function() { selectedSlidersAdd(3);});
Mousetrap.bind('4', function() { selectedSlidersAdd(4);});
Mousetrap.bind('5', function() { selectedSlidersAdd(5);});
Mousetrap.bind('6', function() { selectedSlidersAdd(6);});
Mousetrap.bind('7', function() { selectedSlidersAdd(7);});
Mousetrap.bind('8', function() { selectedSlidersAdd(8);});
Mousetrap.bind('9', function() { selectedSlidersAdd(9);});
Mousetrap.bind('+', function() { selectedSlidersVolUp(0.06);selSliders[10]=0});
Mousetrap.bind('-', function() { selectedSlidersVolDown(0.06);selSliders[10]=0});
Mousetrap.bind('*', function() { selectedSlidersVolUpDown(0.03);selSliders[10]=0});
Mousetrap.bind('/', function() { selectedSlidersFunction(0);});
Mousetrap.bind('enter', function() { selectedSlidersReset();});
Mousetrap.bind('=', function() { selectedSlidersFunction(1);});
Mousetrap.bind('f', function() { experimentalAudioFadeMode();});
Mousetrap.bind('i', function() { enableMidiAssign();});
Mousetrap.bind('ù', function() { experimentalPitchRandom();}); 
Mousetrap.bind('µ', function() { stemDrop(); });
Mousetrap.bind('ç', function() { ranNSliders();});
Mousetrap.bind('del', function() { selectedSlidersZero(1);});
Mousetrap.bind('@', function() { selectedSlidersZero(1);});
Mousetrap.bind('shift+del', function() { selectedSlidersZero(-1);});
Mousetrap.bind('#', function() { selectedSlidersZero(-1);});
Mousetrap.bind('<', function() { selectedSlidersShift(1);});
Mousetrap.bind('>', function() { selectedSlidersShift(-1);});
Mousetrap.bind('g', function() { playAllSounds();setAllLevels();msg("Now Playing...");fCONTEXTSTART=context.currentTime;});
Mousetrap.bind('y', function() { tune(432/440,1);msg("Experimental - Now tuned to A4=432Hz"); });
Mousetrap.bind('?', function() { randomSettings(); });
Mousetrap.bind('c', function() { collectNZ(); });
Mousetrap.bind('shift+c', function() { customGenLaunch(); });
Mousetrap.bind('x c', function() { clearStack(); });
Mousetrap.bind('!', function() { deactivateDynCompressor(); });

// favs
var fData=new Array();

var curGenCode="SPACESHIP";

function favorite(what){
	addToFavorites(what);
	refreshFavs();
}

function addToFavorites(what){
	var ndx=fData.indexOf(what);
	if (ndx==-1){
		$('.c'+what).attr('src','/Pix/fav_b.png');
		fData.push(what);
	}
	else { // is a favorite
		$('.c'+what).attr('src','/Pix/fav.png');
		$('.c'+what+'.titlestar').attr('src','/Pix/fav_grey.png');
		fData.splice(ndx,1);
	}
	fCookieWrite();
}

function fCookieRead(){
	var uids=readCookie('uIDS');
	var cookieName='fSET_'+uids;
	var tmp=readCookie(cookieName);
	if (tmp!=null) fData=JSON.parse(tmp);
}

function fCookieWrite(){
	var uids=readCookie('uIDS');
	var cookieName='fSET_'+uids;
	var days=36500;
	createCookie(cookieName,JSON.stringify(fData),days);
}

function highlightFavs(){
	$('.iFV').css('display', 'inline');
	$('.iFV').prop('title', 'Your favorites');
	$('.iFV').powerTip();
	fCookieRead();
	for (var i in fData) {
  		$('.c'+fData[i]).attr('src','/Pix/fav_b.png');
	}
}

function toggleFavs(){
	if (!highlighted.localeCompare('favs')) { highlighted='none'; $('.hint').parent('span').show();}
	else { highlighted='favs'; $('.hint').parent('span').hide();}
	refreshFavs();

}

function refreshFavs(){
	if (!highlighted.localeCompare('favs')) {
		$('#iFV').attr('src','/Pix/fav_b.png'); // the fav star in the user panel
		for (var i in fData) {
			$('.c'+fData[i]).css('opacity', '1');
			$('.c'+fData[i]).parent('span').show();
		}
  	}
  	else {$('#iFV').attr('src','/Pix/fav_l.png');}
}

function checkFavGen(){
	fCookieRead();
	var ndx=fData.indexOf(curGenCode);
	if (ndx>-1) $('.c'+fData[ndx]).attr('src','/Pix/fav_b.png');
	$('.c'+curGenCode).css('display', 'inline');
    $('.c'+curGenCode).prop('title', 'Favorite');
	$('.c'+curGenCode).powerTip();
}

function addGenToFavs(){
	addToFavorites(curGenCode);
}
	
function addMediaSession() {
			
	// Adding Media Session data
	if ("mediaSession" in navigator) {
	console.log('Adding mediaSession.metadata');

	// TVs constantly hammer the server constantly downloading the file
	// const bogus = new Audio('/Audio/silence' + fileExt); // hosted silence.ogg or silence.mp3
			
	let bogus;
	if (fileExt=='.ogg') { bogus = new Audio('data:audio/ogg;base64,T2dnUwACAAAAAAAAAAA8JkQsAAAAANeDRPYBHgF2b3JiaXMAAAAAAUAfAAAAAAAAsDYAAAAAAACZAU9nZ1MAAAAAAAAAAAAAPCZELAEAAADQKWMvC1r///////////+1A3ZvcmJpczQAAABYaXBoLk9yZyBsaWJWb3JiaXMgSSAyMDIwMDcwNCAoUmVkdWNpbmcgRW52aXJvbm1lbnQpAQAAABIAAABFTkNPREVSPWxpYnNuZGZpbGUBBXZvcmJpcxJCQ1YBAAABAAxSFCElGVNKYwiVUlIpBR1jUFtHHWPUOUYhZBBTiEkZpXtPKpVYSsgRUlgpRR1TTFNJlVKWKUUdYxRTSCFT1jFloXMUS4ZJCSVsTa50FkvomWOWMUYdY85aSp1j1jFFHWNSUkmhcxg6ZiVkFDpGxehifDA6laJCKL7H3lLpLYWKW4q91xpT6y2EGEtpwQhhc+211dxKasUYY4wxxsXiUyiC0JBVAAABAABABAFCQ1YBAAoAAMJQDEVRgNCQVQBABgCAABRFcRTHcRxHkiTLAkJDVgEAQAAAAgAAKI7hKJIjSZJkWZZlWZameZaouaov+64u667t6roOhIasBADIAAAYhiGH3knMkFOQSSYpVcw5CKH1DjnlFGTSUsaYYoxRzpBTDDEFMYbQKYUQ1E45pQwiCENInWTOIEs96OBi5zgQGrIiAIgCAACMQYwhxpBzDEoGIXKOScggRM45KZ2UTEoorbSWSQktldYi55yUTkompbQWUsuklNZCKwUAAAQ4AAAEWAiFhqwIAKIAABCDkFJIKcSUYk4xh5RSjinHkFLMOcWYcowx6CBUzDHIHIRIKcUYc0455iBkDCrmHIQMMgEAAAEOAAABFkKhISsCgDgBAIMkaZqlaaJoaZooeqaoqqIoqqrleabpmaaqeqKpqqaquq6pqq5seZ5peqaoqp4pqqqpqq5rqqrriqpqy6ar2rbpqrbsyrJuu7Ks256qyrapurJuqq5tu7Js664s27rkearqmabreqbpuqrr2rLqurLtmabriqor26bryrLryratyrKua6bpuqKr2q6purLtyq5tu7Ks+6br6rbqyrquyrLu27au+7KtC7vourauyq6uq7Ks67It67Zs20LJ81TVM03X9UzTdVXXtW3VdW1bM03XNV1XlkXVdWXVlXVddWVb90zTdU1XlWXTVWVZlWXddmVXl0XXtW1Vln1ddWVfl23d92VZ133TdXVblWXbV2VZ92Vd94VZt33dU1VbN11X103X1X1b131htm3fF11X11XZ1oVVlnXf1n1lmHWdMLqurqu27OuqLOu+ruvGMOu6MKy6bfyurQvDq+vGseu+rty+j2rbvvDqtjG8um4cu7Abv+37xrGpqm2brqvrpivrumzrvm/runGMrqvrqiz7uurKvm/ruvDrvi8Mo+vquirLurDasq/Lui4Mu64bw2rbwu7aunDMsi4Mt+8rx68LQ9W2heHVdaOr28ZvC8PSN3a+AACAAQcAgAATykChISsCgDgBAAYhCBVjECrGIIQQUgohpFQxBiFjDkrGHJQQSkkhlNIqxiBkjknIHJMQSmiplNBKKKWlUEpLoZTWUmotptRaDKG0FEpprZTSWmopttRSbBVjEDLnpGSOSSiltFZKaSlzTErGoKQOQiqlpNJKSa1lzknJoKPSOUippNJSSam1UEproZTWSkqxpdJKba3FGkppLaTSWkmptdRSba21WiPGIGSMQcmck1JKSamU0lrmnJQOOiqZg5JKKamVklKsmJPSQSglg4xKSaW1kkoroZTWSkqxhVJaa63VmFJLNZSSWkmpxVBKa621GlMrNYVQUgultBZKaa21VmtqLbZQQmuhpBZLKjG1FmNtrcUYSmmtpBJbKanFFluNrbVYU0s1lpJibK3V2EotOdZaa0ot1tJSjK21mFtMucVYaw0ltBZKaa2U0lpKrcXWWq2hlNZKKrGVklpsrdXYWow1lNJiKSm1kEpsrbVYW2w1ppZibLHVWFKLMcZYc0u11ZRai621WEsrNcYYa2415VIAAMCAAwBAgAlloNCQlQBAFAAAYAxjjEFoFHLMOSmNUs45JyVzDkIIKWXOQQghpc45CKW01DkHoZSUQikppRRbKCWl1losAACgwAEAIMAGTYnFAQoNWQkARAEAIMYoxRiExiClGIPQGKMUYxAqpRhzDkKlFGPOQcgYc85BKRljzkEnJYQQQimlhBBCKKWUAgAAChwAAAJs0JRYHKDQkBUBQBQAAGAMYgwxhiB0UjopEYRMSielkRJaCylllkqKJcbMWomtxNhICa2F1jJrJcbSYkatxFhiKgAA7MABAOzAQig0ZCUAkAcAQBijFGPOOWcQYsw5CCE0CDHmHIQQKsaccw5CCBVjzjkHIYTOOecghBBC55xzEEIIoYMQQgillNJBCCGEUkrpIIQQQimldBBCCKGUUgoAACpwAAAIsFFkc4KRoEJDVgIAeQAAgDFKOSclpUYpxiCkFFujFGMQUmqtYgxCSq3FWDEGIaXWYuwgpNRajLV2EFJqLcZaQ0qtxVhrziGl1mKsNdfUWoy15tx7ai3GWnPOuQAA3AUHALADG0U2JxgJKjRkJQCQBwBAIKQUY4w5h5RijDHnnENKMcaYc84pxhhzzjnnFGOMOeecc4wx55xzzjnGmHPOOeecc84556CDkDnnnHPQQeicc845CCF0zjnnHIQQCgAAKnAAAAiwUWRzgpGgQkNWAgDhAACAMZRSSimllFJKqKOUUkoppZRSAiGllFJKKaWUUkoppZRSSimllFJKKaWUUkoppZRSSimllFJKKaWUUkoppZRSSimllFJKKaWUUkoppZRSSimllFJKKaWUUkoppZRSSimllFJKKaWUUkoppZRSSimllFJKKaWUUkoppZRSSimVUkoppZRSSimllFJKKaUAIN8KBwD/BxtnWEk6KxwNLjRkJQAQDgAAGMMYhIw5JyWlhjEIpXROSkklNYxBKKVzElJKKYPQWmqlpNJSShmElGILIZWUWgqltFZrKam1lFIoKcUaS0qppdYy5ySkklpLrbaYOQelpNZaaq3FEEJKsbXWUmuxdVJSSa211lptLaSUWmstxtZibCWlllprqcXWWkyptRZbSy3G1mJLrcXYYosxxhoLAOBucACASLBxhpWks8LR4EJDVgIAIQEABDJKOeecgxBCCCFSijHnoIMQQgghREox5pyDEEIIIYSMMecghBBCCKGUkDHmHIQQQgghhFI65yCEUEoJpZRSSucchBBCCKWUUkoJIYQQQiillFJKKSGEEEoppZRSSiklhBBCKKWUUkoppYQQQiillFJKKaWUEEIopZRSSimllBJCCKGUUkoppZRSQgillFJKKaWUUkooIYRSSimllFJKCSWUUkoppZRSSikhlFJKKaWUUkoppQAAgAMHAIAAI+gko8oibDThwgMQAAAAAgACTACBAYKCUQgChBEIAAAAAAAIAPgAAEgKgIiIaOYMDhASFBYYGhweICIkAAAAAAAAAAAAAAAABE9nZ1MAAAD+AAAAAAAAPCZELAIAAACdXgvI/wEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAE9nZ1MAAAD9AQAAAAAAPCZELAMAAABgPVAd/wEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAE9nZ1MAAAD8AgAAAAAAPCZELAQAAABnKp7R/wEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAE9nZ1MAAAD7AwAAAAAAPCZELAUAAAACYuTF/wEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAE9nZ1MAAAD6BAAAAAAAPCZELAYAAAA3vaYW/wEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAE9nZ1MAAAD5BQAAAAAAPCZELAcAAADK3v3D/wEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAE9nZ1MAAAD4BgAAAAAAPCZELAgAAACTw7Ti/wEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAE9nZ1MABABTBwAAAAAAPCZELAkAAABeJ+eUWwEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'); }
	else {
	bogus = new Audio('data:audio/mp3;base64,SUQzAwAAAAAAFgAAAAAAAAAAAAAAAAAAAAAAAAAAAAD/4xjEAAAAA0gAAAAATEFNRTMuMTAwVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjEOwAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjEdgAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjEsQAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVX/4xjExAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVU=');
		}
			
	bogus.loop=true;
	bogus.volume=0.01; // must be >0 for MediaSession to activate
	bogus.preload="auto";
	
	bogus.oncanplaythrough=function() {
		bogus.play().catch(e=>console.warn("Silent play failed:",e));
	};
	
	document.body.appendChild(bogus);
	
	navigator.mediaSession.metadata=new MediaMetadata({
		title:"Warp Speed",
		artist:"myNoise",
		album:"Focus • Relax • Sleep",
		artwork:[
			{src:"https://myNoise.net/Data/SPACESHIP/album@128.jpg",sizes:"128x128",type:"image/jpeg"},
			{src:"https://myNoise.net/Data/SPACESHIP/album@256.jpg",sizes:"256x256",type:"image/jpeg"},
			{src:"https://myNoise.net/Data/SPACESHIP/album@512.jpg",sizes:"512x512",type:"image/jpeg"}
		]
	});
	navigator.mediaSession.setActionHandler("play",function(){toggleMute();});
	navigator.mediaSession.setActionHandler("pause",function(){toggleMute();});
	navigator.mediaSession.setActionHandler("previoustrack",function(){resetSliders();});
	navigator.mediaSession.setActionHandler("nexttrack",function(){randomSettings();});

		}
}

/* Periodically check and resume the AudioContext
setInterval(() => {
    if (context.state === 'suspended') {
        context.resume().then(() => {
            console.log('AudioContext resumed.');
        }).catch(err => {
            console.warn('AudioContext resume failed:', err);
        });
    } else {
        // console.log('AudioContext is running.');
    }
}, 1000); // every second
*/

