#NAME: Weijia Shi, Zheng Wang
#EMAIL: swj0419@g.ucla.edu, wangz980702@g.ucla.edu
#ID: 104757423, 404855295

default:
	cp lab3b.py lab3b
	chmod +x lab3b.py lab3b

dist: default
	tar -zvcf lab3b-104757423.tar.gz lab3b.py Makefile README

clean:
	rm -f *.tar.gz lab3b

