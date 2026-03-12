import CoreAudio

var address = AudioObjectPropertyAddress(
    mSelector: kAudioHardwarePropertyDefaultInputDevice,
    mScope: kAudioObjectPropertyScopeGlobal,
    mElement: kAudioObjectPropertyElementMain
)
var deviceID: AudioDeviceID = 0
var size = UInt32(MemoryLayout<AudioDeviceID>.size)
AudioObjectGetPropertyData(AudioObjectID(kAudioObjectSystemObject), &address, 0, nil, &size, &deviceID)

var running: UInt32 = 0
var runAddr = AudioObjectPropertyAddress(
    mSelector: kAudioDevicePropertyDeviceIsRunningSomewhere,
    mScope: kAudioObjectPropertyScopeInput,
    mElement: kAudioObjectPropertyElementMain
)
var runSize = UInt32(MemoryLayout<UInt32>.size)
AudioObjectGetPropertyData(deviceID, &runAddr, 0, nil, &runSize, &running)
// Exit 0 = mic active, exit 1 = mic inactive
exit(running == 1 ? 0 : 1)
