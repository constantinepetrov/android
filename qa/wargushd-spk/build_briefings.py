#!/usr/bin/env python3
"""Build an owner-only WargusHD v3.4.91 campaign-briefing voice add-on.

Source is the user-provided SPK localization Speech_SPK.zip, originally shared
by war2.ru in a public Drive folder. Audio and official game data never go
into the Git repository. Original files are not edited or executed.

Compatibility format is adapted from the actual WargusHD 3.4.91
lt-tod-briefings v1.0.6 downloaded from the app's own mod catalog.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from io import BytesIO
import hashlib
import json
from pathlib import Path
import re
import subprocess
from zipfile import ZipFile, ZIP_DEFLATED

SR=44100
BITRATE="128k"
PAUSE_MS=180
WAV_PATTERNS=[
    (re.compile(r"^Speech/(hum|orc)_(\d+)_(\d+)\.wav$", re.I), "base"),
    (re.compile(r"^Speech/War2x/(hum|orc)(\d+)_(\d+)\.wav$", re.I), "expansion"),
    (re.compile(r"^Speech/(hum|orc)vict\.wav$", re.I), "base-end"),
    (re.compile(r"^Speech/War2x/(hum|orc)vict(\d+)\.wav$", re.I), "expansion-end"),
]
EXPECTED={"human":14,"orc":14,"xhuman":12,"xorc":12}


def clip_pcm(blob: bytes) -> bytes:
    p=subprocess.run(
        ["ffmpeg","-nostdin","-hide_banner","-loglevel","error",
         "-i","pipe:0","-map","0:a:0","-ac","1","-ar",str(SR),
         "-c:a","pcm_s16le","-f","s16le","pipe:1"],
        input=blob,capture_output=True)
    if p.returncode or not p.stdout:
        raise RuntimeError("Failed to decode input WAV: "+p.stderr.decode(errors="replace")[-400:])
    return p.stdout

def encode_mp3(raw: bytes) -> bytes:
    p=subprocess.run(
        ["ffmpeg","-nostdin","-hide_banner","-loglevel","error",
         "-f","s16le","-ar",str(SR),"-ac","1","-i","pipe:0",
         "-c:a","libmp3lame","-b:a",BITRATE,"-id3v2_version","0",
         "-f","mp3","pipe:1"],
        input=raw,capture_output=True)
    if p.returncode or not p.stdout:
        raise RuntimeError("MP3 encoding failed: "+p.stderr.decode(errors="replace")[-400:])
    return p.stdout

def route(path: str):
    for regex,kind in WAV_PATTERNS:
        m=regex.fullmatch(path)
        if not m:continue
        who="human" if m.group(1).lower()=="hum" else "orc"
        if kind=="base":return who,str(int(m.group(2))),int(m.group(3))
        if kind=="expansion":return "x"+who,str(int(m.group(2))),int(m.group(3))
        if kind=="base-end":return who,"end",1
        if kind=="expansion-end":return "x"+who,"end",int(m.group(2))
    raise RuntimeError("Unrecognized original SPK speech file name: "+path)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--source",required=True,type=Path)
    ap.add_argument("--out",required=True,type=Path)
    ap.add_argument("--report",required=True,type=Path)
    args=ap.parse_args()
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.report.parent.mkdir(parents=True,exist_ok=True)
    grouped=defaultdict(list)
    with ZipFile(args.source) as source:
        entries=[i for i in source.infolist() if not i.is_dir()]
        if source.testzip() is not None:
            raise RuntimeError("Original SPK ZIP has a damaged member")
        if len(entries)!=104:
            raise RuntimeError("Expected exactly 104 SPK audio files, found "+str(len(entries)))
        for entry in entries:
            if not entry.filename.lower().endswith(".wav"):
                raise RuntimeError("Unexpected non-WAV file: "+entry.filename)
            camp,mission,segment=route(entry.filename)
            grouped[(camp,mission)].append((segment,entry.filename))
    if len(grouped)!=56:raise RuntimeError(f"Expected 56 campaigns briefings, found {len(grouped)}")
    for camp,num in EXPECTED.items():
        actual={m for c,m in grouped if c==camp}
        expected={str(i) for i in range(1,num+1)}|{"end"}
        if actual!=expected:
            raise RuntimeError(f"{camp} missing={expected-actual} extra={actual-expected}")
    for key,items in grouped.items():
        indices=[j for j,_ in items]
        if len(indices)!=len(set(indices)) or sorted(indices)!=list(range(1,max(indices)+1)):
            raise RuntimeError("Missing/duplicate speech part: "+str(key)+str(indices))
    data={"format":1,"briefing":{}}
    claims=[]
    total_duration=0
    with ZipFile(args.source) as source, ZipFile(args.out,"w",ZIP_DEFLATED,compresslevel=6) as dest:
        for camp in EXPECTED:
            group={}
            for mission in [str(i) for i in range(1,EXPECTED[camp]+1)]+["end"]:
                chunks=[]
                for segment,name in sorted(grouped[(camp,mission)]):
                    chunks.append(clip_pcm(source.read(name)))
                pause=b"\x00"*int(SR*2*PAUSE_MS/1000)
                combined=pause.join(chunks)
                total_duration+=len(combined)/(SR*2)
                mp3=encode_mp3(combined)
                path=f"sounds/briefing/{camp}_{mission}.mp3"
                dest.writestr(path,mp3)
                group[mission]=[path]
                claims.append(f"voice:briefing:{camp}:{mission}")
            data["briefing"][camp]=group
        mod={
            "format":1,
            "id":"russian-spk-briefings",
            "ns":"spb",
            "name":"Russian Classic SPK - Campaign Briefings",
            "version":"1.0.0",
            "author":"SPK (original dubbing); war2.ru (Remastered adaptation)",
            "description":"Classic Russian SPK narration for all four Warcraft II campaign sets, including Beyond the Dark Portal.",
            "categories":["audio","campaign"],
            "kinds":["briefing-voice"],
            "requires":["mod-path","voice-override"],
            "scope":{"campaign":True,"custom":False,"lan":False},
            "entry":{"defs":["defs/voices.json"],"script":None},
            "provides":["defs","sounds"],
            "gameplay":False,
            "contains_game_derived":False,
            "claims":claims
        }
        dest.writestr("mod.json",json.dumps(mod,ensure_ascii=False,indent=2)+"\n")
        dest.writestr("defs/voices.json",json.dumps(data,ensure_ascii=False,indent=2)+"\n")
    with ZipFile(args.out) as z:
        if z.testzip() is not None:raise RuntimeError("Generated ZIP CRC failed")
        assert len(z.namelist())==58
        manifest=json.loads(z.read("mod.json"))
        voices=json.loads(z.read("defs/voices.json"))
        assert len(voices["briefing"])==4 and manifest["id"]=="russian-spk-briefings"
        for camp,group in voices["briefing"].items():
            for mission,paths in group.items():
                for p in paths:
                    assert z.getinfo(p).file_size>1000
    mp3_bytes=args.out.stat().st_size
    h=hashlib.sha256()
    with args.out.open("rb") as f:
        for block in iter(lambda:f.read(1024*1024),b""):h.update(block)
    report={
        "status":"ARCHIVE_CREATED_AND_CRC_VERIFIED",
        "source_audio_fragments":len(entries),
        "campaign_audio_tracks":len(grouped),
        "zip_entries":58,
        "archives":{"original_source_bytes":args.source.stat().st_size,"mod_zip_bytes":mp3_bytes},
        "audio":{"codec":"MP3","bitrate":BITRATE,"sample_rate_hz":SR,"channels":1,"inter_fragment_pause_ms":PAUSE_MS,
                 "total_minutes":round(total_duration/60,2)},
        "sha256":h.hexdigest(),
        "branch_safe":True,
        "on_device_verified":False,
        "mod_id":manifest["id"],
        "original_game_data_modified":False,
        "distribution":"Private owner-only GitHub draft release"
    }
    args.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print("SPEECH_MOD_REPORT",json.dumps(report,ensure_ascii=False),flush=True)

if __name__=="__main__":
    main()
