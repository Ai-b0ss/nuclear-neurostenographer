#!/bin/bash
# usage: run_one.sh <a0|a3>
M=$1; export MSYS_NO_PATHCONV=1; A="K:/nn-release-keys/adb/adb.exe -s AKPNU20B24113866"; O=K:/nn-asr-phone/out; mkdir -p $O
$A shell 'dumpsys battery | grep -E "level|temperature"' > $O/$M.batt_before.txt
date +%s > $O/$M.t0
$A shell "cd /data/local/tmp/nnbench && LD_LIBRARY_PATH=/data/local/tmp/nnbench/lib CLASSPATH=/data/local/tmp/nnbench/classes.dex app_process / PhoneAsrBench $M /data/local/tmp/nnbench/$M /data/local/tmp/nnbench/wav /data/local/tmp/nnbench/holdout.txt 4 /data/local/tmp/nnbench/$M.tsv" > $O/$M.stdout.txt 2>&1
echo "exit=$?" >> $O/$M.stdout.txt
date +%s > $O/$M.t1
$A shell 'dumpsys battery | grep -E "level|temperature"' > $O/$M.batt_after.txt
$A pull /data/local/tmp/nnbench/$M.tsv $O/$M.tsv
