#!/bin/bash

if [ ! -z $SUBMIT_PWD ]; then
    cd $SUBMIT_PWD
fi

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

test=$(python3 benchmark.py list set:com-pile-bench)

c=0
cores=16
t=0
lim=100

# if $1 not empty, use as upper limit
if [ ! -z $1 ]; then
    lim=$1
fi

# if $OMP_NUM_THREADS not empty, use as number of cores
if [ ! -z $OMP_NUM_THREADS ]; then
    cores=$OMP_NUM_THREADS
fi

# if $2 not empty, use as number of cores
if [ ! -z $2 ]; then
    cores=$2
fi

trap 'jobs -p | xargs -I{} kill -- {}; echo "killed jobs"; exit' INT

echo "Synthesizing patterns"

mkdir -p output

for i in $(echo $test | sed "s/,/ /g")
do
    python3 benchmark.py run --tests=$i set:com-pile-bench synth:len-cegis |& tee output/$i.out &
    c=$((c+1))
    t=$((t+1))
    if [ $c -eq $cores ]; then
        wait
        c=0
    fi
    if [ $t -eq $lim ]; then
        wait
        break
    fi
done

wait

echo "Done"
