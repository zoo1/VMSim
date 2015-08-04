import argparse
import sys

#used to check the argument format
def args():
	parser = argparse.ArgumentParser(description='Virtual Memory Simulator for Opt, Clock, Aging, and LRU')
	parser.add_argument("-n", "--numframes", type=int, required=True, help="Number of frames")
	parser.add_argument("-a", "--alg", type=str, required=True, choices=['opt', 'clock', 'aging', 'lru'], help="Specified algorithm")
	parser.add_argument("-r", "--refresh", type=int, help="Refresh interval in units of number of refernces")
	parser.add_argument("tracefile", help="Name of the tracefile", type=str)
	return parser.parse_args()

#Class for each entry in ram/pagetable
class Entry:
	def __init__(self, addr):
		self.fn = -1 #frame number
		self.d = False #dirty bit
		self.r = False #referenced bit
		self.v = False #valid bit
		self.addr = addr #page addr
	def __str__(self):
		ret=""+str(self.addr)+" "+str(self.fn)+" "+str(self.d)+" "+str(self.fn)+" "+str(self.r)
		return ret
	def evict(self):
		self.d = False
		self.r = False
		self.v = False
		self.fn = -1
	def added(self):
		self.r = True
		self.v = True

#ram used for optimal algorithm
class optram:
	def __init__(self, numframes, filename):
		self.array = {}
		self.nf = numframes
		self.fc = 0 
		self.addrmap = self.initmap(filename)

	def __str__(self):
		ret=""
		for keys,values in self.array.items():
			ret+=str(keys) + ": " + str(values)+"\n"
		return ret
	#starting out adding until fills up
	def add(self, entry, index):
		self.array[index] = entry
		self.addrmap[entry.addr].pop(0)
		entry.added()
		entry.fn=index
		self.fc += 1
	#adding new 
	def hit(self, entry, index):
		self.array[index] = entry
		self.addrmap[entry.addr].pop(0)
		entry.added()
	def is_full(self):
		return (int(self.fc) >= int(self.nf))
	def evict(self, newpage):
		found=True
		ret=0
		def func(p):
   			return self.addrmap[self.array[p].addr][0]
   		index = max(self.array, key=func)
   		if(self.array[index].d):
				ret=1
		newpage.fn=index
		self.array[index].evict()
		self.array[index]=newpage
		newpage.added()
		self.addrmap[newpage.addr].pop(0)
		return ret
	#used to initialize map to remove multiple reads from disk
	def initmap(self, filename):
		ret = {}
		f = open(filename, "r")
		lineid=0
		for line in f:
			linecontents = line.split()
			addr = str(linecontents[0][:5])
			if(addr in ret):
				ret[addr].append(lineid)
			else:
				ret[addr]=[lineid]
			lineid+=1
		f.close()
		for keys,values in ret.items():
			ret[keys].append(sys.maxint)
		return ret

#ram class used for clock algorithm
class clkram:
	def __init__(self, numframes):
		self.array = {}
		self.nf = numframes
		self.fc = 0
		self.clock_hand = 0
		self.clockarr = []

	def __str__(self):
		ret=""
		for keys,values in self.array.items():
			ret+=str(keys) + ": " + str(values)+"\n"
		return ret
	#starting out adding until fills up
	def add(self, entry, index):
		self.array[index] = entry
		self.clockarr.append(entry)
		entry.added()
		entry.fn=index
		self.fc += 1
	#adding new 
	def hit(self, entry, index):
		self.array[index] = entry
		entry.added()
	def is_full(self):
		return (int(self.fc) >= int(self.nf))
	def evict(self, newpage):
		found=True
		ret=0
		while(found):
			if(self.clockarr[self.clock_hand].r):
				self.clockarr[self.clock_hand].r=False
			else:
				if(self.clockarr[self.clock_hand].d):
					ret=1
				newpage.fn=self.clockarr[self.clock_hand].fn
				self.clockarr[self.clock_hand].evict()
				found=False
				self.clockarr[self.clock_hand]=newpage
				self.array[newpage.fn]=newpage
				newpage.added()
			self.clock_hand+=1
			if(self.clock_hand==self.nf):
				self.clock_hand=0
		return ret

#ram class used for aging algorithm
class ageram:
	def __init__(self, numframes):
		self.array = {}
		self.nf = numframes
		self.fc = 0 #used for initial allocation
		self.agearr = []

	def __str__(self):
		ret=""
		for keys,values in self.array.items():
			ret+=str(keys) + ": " + str(values)+"\n"
		return ret
	#starting out adding until fills up
	def add(self, entry, index):
		self.array[index] = entry
		self.agearr.append(0x00)
		entry.added()
		entry.fn=index
		self.fc += 1
	#adding new 
	def hit(self, entry, index):
		self.array[index] = entry
		entry.added()
	def is_full(self):
		return (int(self.fc) >= int(self.nf))
	def evict(self, newpage):
		ret=0
		exists=False
		for keys,values in self.array.items():
			if(not values.r):
				exists=True
		if(exists):
			minv=sys.maxint
			for keys,values in self.array.items():
				if(not values.r):
					if(self.agearr[keys]<minv):
						minv=self.agearr[keys]
			index = self.agearr.index(minv)
			if(self.array[index].d):
				ret=1
			newpage.fn=index
			self.array[index].evict()
			self.array[index]=newpage
			self.agearr[index]=0x00
			newpage.added()
		else: #all are 1 so check every one for the min
			index = self.agearr.index(min(self.agearr))
			if(self.array[index].d):
				ret=1
			newpage.fn=index
			self.array[index].evict()
			self.array[index]=newpage
			self.agearr[index]=0x00
			newpage.added()
		return ret
	def refresh(self):
		for keys,values in self.array.items():
			self.agearr[keys]=self.agearr[keys] >> 1
			if(values.r):
				self.agearr[keys] |= 0x80
			values.r=False

#ram class used for lru
class lruram:
	def __init__(self, numframes):
		self.array = {}
		self.nf = numframes
		self.fc = 0
		self.ticker = 0
		self.lruarr = []

	def __str__(self):
		ret=""
		for keys,values in self.array.items():
			ret+=str(keys) + ": " + str(values)+"\n"
		return ret
	#starting out adding until fills up
	def add(self, entry, index):
		self.array[index] = entry
		self.lruarr.append(self.ticker)
		self.ticker+=1
		entry.added()
		entry.fn=index
		self.fc += 1
	#adding new 
	def hit(self, entry, index):
		self.array[index] = entry
		entry.added()
		self.lruarr[index]=self.ticker
		self.ticker+=1
	def is_full(self):
		return (int(self.fc) >= int(self.nf))
	def evict(self, newpage):
		ret=0
		index = self.lruarr.index(min(self.lruarr))
		if(self.array[index].d):
			ret=1
		newpage.fn=index
		self.array[index].evict()
		self.array[index]=newpage
		newpage.added()
		self.lruarr[index]=self.ticker
		self.ticker+=1
		return ret

def main():
	arg = args()
	#mapping for algorithm
	mapping = {'opt': ['Optimal', optram], 'clock': ['Clock', clkram], 'aging': ['Aging',ageram], 'lru': ['Least Recently Used',lruram]}
	if(arg.alg == 'aging'):
		if(not arg.refresh):
			print "refresh amount needs to be set when using aging"
			exit(1)
	if(arg.alg == 'opt'):
		Ram = mapping[arg.alg][1](arg.numframes,arg.tracefile)
	else:
		Ram = mapping[arg.alg][1](arg.numframes)
	PageTable = {}
	totalmemacces=0
	totalpagefault=0
	totaldiskwrite=0
	
	#open file
	f = open(arg.tracefile, "r")
	for line in f:
		totalmemacces += 1
		linecontents = line.split()
		addr = str(linecontents[0][:5])
		rw = linecontents[1]
		#check for existance in page table
		if( addr in PageTable ):
			#check if valid,we have a hit
			if(PageTable[addr].v):
				if(rw=='W'):
					PageTable[addr].d=True
				Ram.hit(PageTable[addr], PageTable[addr].fn)
				print "hit"
			else:
				if(Ram.is_full()):
					totalpagefault += 1
					if(rw=='W'):
						PageTable[addr].d=True
					if(Ram.evict(PageTable[addr])==1):
						totaldiskwrite+=1
						print "page fault - evict dirty"
					else:
						print "page fault - evict clean"
				else:
					totalpagefault += 1
					entry = PageTable[addr]
					if(rw=='W'):
						entry.d=True
					Ram.add(newentry,Ram.fc)
					print "page fault - no eviction"
		else:
			if(Ram.is_full()):
				totalpagefault += 1
				newentry = Entry(addr)
				PageTable[addr]= newentry
				if(rw=='W'):
					newentry.d=True
				if(Ram.evict(newentry)==1):
					totaldiskwrite+=1
					print "page fault - evict dirty"
				else:
					print "page fault - evict clean"

			else:
				#add to ram
				totalpagefault += 1
				newentry = Entry(addr)
				if(rw=='W'):
					newentry.d=True
				Ram.add(newentry,Ram.fc)
				#add to page table
				PageTable[addr]= newentry
				print "page fault - no eviction"
		if(arg.alg == 'aging' and (totalmemacces % arg.refresh==0)):
			Ram.refresh()
	f.close()
	print "+++++++++++++++++++++++++++++++++"
	print "Algorithm: " + mapping[arg.alg][0]
	print "Number of Frames: " + str(arg.numframes)
	print "Total Memory Accesses: " + str(totalmemacces)
	print "Total Page Faults: " + str(totalpagefault)
	print "Total Writes to Disk: " + str(totaldiskwrite)
	print "+++++++++++++++++++++++++++++++++"

if __name__ == "__main__":
    main()