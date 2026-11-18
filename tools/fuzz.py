import base64, json, random, sys
random.seed(int(sys.argv[1]))
H = ["Serial No","Invoice Date","Tax Invoice No","Supplier's TIN","Name of the Supplier","Description","Value of purchase","VAT Amount","Disallowed VAT Amount"]
vals = {
 0: ['1','2','01','0','-3',' 4','0x1A','#ff','&h10','99999999999','2147483647','2147483648','abc','','+5','1.0'],
 1: ['10/05/2026','1/5/2026','02/29/2024','02/29/2026','13/01/2026','2026-10-05','10/5/26','', ' 10/05/2026','12/31/2019','06/28/2022','09/15/2022','01/28/2024','05/01/2016','07/12/2016','11/30/2026','10/31/2026'],
 2: ['INV-1','inv-1','A 1','A.1','#7','x'*40,'x'*41,'a/b_c-d','', 'Ä1'],
 3: ['100000024','100000032','100000025','100000016','149000005','149002623','10000002','100000024-7000',' 100000024',''],
 4: ['Sup','"Quoted"','N'*100,'N'*101,'Śrī','', 'a\tb'],
 5: ['D','D'*500,'D'*501,''],
 6: ['5000.00','5000','5000.001','5000.100','-5000.00','1e3','1,000.00','.5','5.','5000-','123456789012345','1234567890123456','0','  5000.00','0.00','100.10','3333.33','999999999999.99'],
 7: ['900.00','900','900.99','901.00','899.01','0.00','750','750.00','-900','1e2','600.00','400.00','0.09','18.02','599.99','1.5'],
 8: ['0.00','0','900.00','900.01','-1','',' 0','1e0','0.001'],
}
cases=[]
for i in range(int(sys.argv[2])):
    n = random.randint(0,6)
    rows=[]
    for r in range(n):
        base=[str(r+1),'10/05/2026',f'INV-{r}','100000024','Sup','D','5000.00','900.00','0.00']
        for _ in range(random.randint(0,3)):
            c=random.randint(0,8); base[c]=random.choice(vals[c])
        rows.append(base)
    h=H[:]
    if random.random()<0.1: random.shuffle(h)
    if random.random()<0.05: h=h[:8]
    if random.random()<0.05: h=h+['']
    eol=random.choice(['\r\n','\n','\r'])
    body=eol.join([','.join(h)]+[','.join(r) for r in rows])+(eol if random.random()<.8 else '')
    b=body.encode()
    if random.random()<0.1: b=b'\xef\xbb\xbf'+b
    if random.random()<0.05: b='﻿'.encode('utf-16-le')+body.encode('utf-16-le')
    period=random.choice(['2641']*8+['2640','2631','2643','2410','2411','2603','','2644','02641','1941','2241','2240'])
    fname=random.choice(['100000016_VAT_SCHEDULE02_{p}_20261119_ORIGINAL_V1.csv']*12+['100000016_VAT_SCHEDULE02_{p}_20261119_ORIGINAL_V1.csv','100000016_vat_schedule02_{p}_20261119_original_v2.CSV',
      '100000017_VAT_SCHEDULE02_{p}_20261119_ORIGINAL_V1.csv','100000016_VAT_SCHEDULE02_{p}_2026119_ORIGINAL_V1.csv',
      '100000016_VAT_SCHEDULE02_26(1_20261119_ORIGINAL_V1.csv','100000016_VAT_SCHEDULE02_{p}_20261119_ORIGINAL_V1.csv.txt','x_y','100000016_VAT_SCHEDULE02_{p}_20261119_ORIGINAL_V.csv']).format(p=period or '2641')
    cases.append(dict(name=f'f{i}',file=fname,b64=base64.b64encode(b).decode(),period=period))
json.dump(dict(cases=cases),sys.stdout)
