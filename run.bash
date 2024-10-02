#!/bin/bash

test=$(python3 bitvec_benchmarks/compile_patterns.py patterns -T)

c=0
cores=16
t=0
lim=100

# if $1 not empty, use as upper limit
if [ ! -z $1 ]; then
    lim=$1
fi

# if $2 not empty, use as number of cores
if [ ! -z $2 ]; then
    cores=$2
fi

echo "Compiling patterns"

for i in $(echo $test | sed "s/,/ /g")
do
    python3 bitvec_benchmarks/compile_patterns.py patterns -t $i |& tee $i.out &
    c=$((c+1))
    t=$((t+1))
    if [ $c -eq cores ]; then
        wait
        c=0
    fi
    if [ $t -eq lim ]; then
        wait
        break
    fi
done

echo "Done"
