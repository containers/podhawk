import subprocess
import os
images = subprocess.Popen(["podman","images"],   
            stdout=subprocess.PIPE, 
            stderr=subprocess.STDOUT)
stdout,stderr = images.communicate()
stdout=stdout.split()
imagelist=[]  #This stores the list of images currently in the local machine
for i in range(6, len(stdout), 8):
	imagelist.append(stdout[i])

containers = subprocess.Popen(["podman","ps"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT)
stdout,stderr = containers.communicate()

containerlist=[]  #This list stores the names of all the running containers
runningimages=[]  #This list stores the names of all the running images
count=1
for item in stdout.split('\n'): #Spliting on the basis of new line
	if count==1:		#Skips the first line which contains the column names
		count=count+1
		continue
	else:
		if len(item)<=1: 
			continue
		listing=item.split(' ') #Splits on the basis of space
		#x=listing[2].split(':') #This line can be uncommented if you want to download the image with the latest tag irrespective of the current tag
		
		containerlist.append(listing[0])
		runningimages.append(listing[2])
		#runningimages.append(x[0]) #This line can be uncommented and the previous line has to be commented to download the image with the latest tag irrespective of the current tag


containerinfo=[]  #Stores the image ids of the images which are currently running on the containers

for i in range(0, len(containerlist)):
	temp_info = subprocess.Popen(["podman","inspect",containerlist[i]],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT)
	stdout,stderr = temp_info.communicate()
	for item in stdout.split('\n'):
		if "Image" in item:
			x=item.strip()
			break
	x=x.split(':')
	x=x[1].split('"')
	x=x[1]
	containerinfo.append(x)

newimages=[]		#This list stores all the new pulled images corresponding to the running images
for i in range(0, len(runningimages)):
	pull = subprocess.Popen(["podman","pull",runningimages[i]],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT)
        stdout,stderr = pull.communicate()
	stdout=stdout.split('\n')
	stdout=stdout[-2]
	newimages.append(stdout)	

for i in range(0, len(containerlist)):
	if(containerinfo[i]!=newimages[i]): 				#Compares the new image ids with the current image ids
		os.system("podman "+"stop "+containerlist[i])		#Stopping the container
		os.system("podman "+"rm "+containerlist[i])		#Deleting the container
		pull = subprocess.Popen(["podman","create",runningimages[i]],	#Create a new container with the new image
            		stdout=subprocess.PIPE,
            		stderr=subprocess.STDOUT)
        	stdout,stderr = pull.communicate()
		os.system("podman "+"start "+stdout)				#Starting the new container
