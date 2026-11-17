import sys, zipfile, collections
for p in sys.argv[1:]:
    z = zipfile.ZipFile(p)
    l = z.namelist()
    print(p, len(l), l[:4], l[-2:])
    print(collections.Counter(x.rsplit('.', 1)[-1].lower() if '.' in x else '<dir>' for x in l))
    print('uncompressed MB', sum(i.file_size for i in z.infolist()) / 1e6)
