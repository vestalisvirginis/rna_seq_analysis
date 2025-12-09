#pharokka.py -i /data/valentinas_phages/spbeta_m1_1_s7.fa -o /data/valentinas_pharokka/spbeta_m1_1_s7 -d /data/pharokka_db_install/ -t 20 -p spbeta_m1_1_s7 -g prodigal-gv --dnaapler

#pharokka.py -i /data/valentinas_phages/spbeta_m1_2_s8.fa -o /data/valentinas_pharokka/spbeta_m1_2_s8 -d /data/pharokka_db_install/ -t 20 -p spbeta_m1_2_s8 -g prodigal-gv --dnaapler

#pharokka.py -i /data/valentinas_phages/spbeta_m1_3_s9.fa -o /data/valentinas_pharokka/spbeta_m1_3_s9 -d /data/pharokka_db_install/ -t 20 -p spbeta_m1_3_s9 -g prodigal-gv --dnaapler

#pharokka.py -i /data/valentinas_phages/spbeta_m2_1_s10.fa -o /data/valentinas_pharokka/spbeta_m2_1_s10 -d /data/pharokka_db_install/ -t 20 -p spbeta_m2_1_s10 -g prodigal-gv --dnaapler

#pharokka.py -i /data/valentinas_phages/spbeta_m2_2_s11.fa -o /data/valentinas_pharokka/spbeta_m2_2_s11 -d /data/pharokka_db_install/ -t 20 -p spbeta_m2_2_s11 -g prodigal-gv --dnaapler

#pharokka.py -i /data/valentinas_phages/spbeta_m2_3_s12.fa -o /data/valentinas_pharokka/spbeta_m2_3_s12 -d /data/pharokka_db_install/ -t 20 -p spbeta_m2_3_s12 -g prodigal-gv --dnaapler




#phold run -i /data/valentinas_pharokka/spbeta_m1_1_s7/spbeta_m1_1_s7.gbk -o /data/valentinas_phold/spbeta_m1_1_s7  -t 20 -p spbeta_m1_1_s7 -d /db/ --finetune --keep_tmp_files --cpu

#phold run -i /data/valentinas_pharokka/spbeta_m1_2_s8/spbeta_m1_2_s8.gbk -o /data/valentinas_phold/spbeta_m1_2_s8  -t 20 -p spbeta_m1_2_s8 -d /db/ --finetune --keep_tmp_files --cpu

#phold run -i /data/valentinas_pharokka/spbeta_m1_3_s9/spbeta_m1_3_s9.gbk -o /data/valentinas_phold/spbeta_m1_3_s9  -t 20 -p spbeta_m1_3_s9 -d /db/ --finetune --keep_tmp_files --cpu

#phold run -i /data/valentinas_pharokka/spbeta_m2_1_s10/spbeta_m2_1_s10.gbk -o /data/valentinas_phold/spbeta_m2_1_s10  -t 20 -p spbeta_m2_1_s10 -d /db/ --finetune --keep_tmp_files --cpu

#phold run -i /data/valentinas_pharokka/spbeta_m2_2_s11/spbeta_m2_2_s11.gbk -o /data/valentinas_phold/spbeta_m2_2_s11  -t 20 -p spbeta_m2_2_s11 -d /db/ --finetune --keep_tmp_files --cpu

#phold run -i /data/valentinas_pharokka/spbeta_m2_3_s12/spbeta_m2_3_s12.gbk -o /data/valentinas_phold/spbeta_m2_3_s12  -t 20 -p spbeta_m2_3_s12 -d /db/ --finetune --keep_tmp_files --cpu





docker cp temp/cnn_chkpnt_finetune/phold_db_model.pth phold:/usr/local/lib/python3.11/site-packages/phold/cnn/cnn_chkpnt_finetune/
docker cp temp/cnn_chkpnt_finetune/vanilla_model.pth phold:/usr/local/lib/python3.11/site-packages/phold/cnn/cnn_chkpnt_finetune/



docker run -it --rm --name phold -v $PWD/databases/:/db -v $PWD/temp/:/data phold bash
mkdir /usr/local/lib/python3.11/site-packages/phold/cnn/cnn_chkpnt_finetune/
