#!/bin/bash

trap "exit" INT
OUTPUT_FILE='dig_test_d1_d3_r256_i2000_t100ms.csv'
for i in {1..2300};do
  dig +short d3 | awk 'ORS=FS' >> $OUTPUT_FILE
  printf ',' >> $OUTPUT_FILE
  date +'%Y_%m_%d_%H_%M_%S' >> $OUTPUT_FILE
  sleep .1
done