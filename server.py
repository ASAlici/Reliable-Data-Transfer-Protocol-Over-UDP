import socket
import random as rd
import select 
import time 


server_ip = "127.0.0.1"
server_port = 10001
client_port = 10000
serverfilename="sorrowful_be_the_heart_penitent_one"
timeoutTime=0.0001
serverfile=""
windowSize=-1
errorRate=-1


def recieveWithTimeout(sock):
    
    readable, _, _ = select.select([sock], [], [], 0.0001)
    for sock in readable:
        data, address = sock.recvfrom(1024)
        return bytearray(data)
    return None

def makeHandshakePacket(filename):
    filenameAsByteArr=bytearray(filename,"utf-8")
    packet=bytearray([0,len(filenameAsByteArr)])
    packet+=filenameAsByteArr
    return bytes(packet)

def makeACKPacket(sequenceNumber):
    return bytes(bytearray([1,sequenceNumber]))
    

def makeDATAPacket(dataAsByteArr:bytearray,sequenceNumber:int):
    #dataAsByteArr=bytearray(data.to_bytes( (data.bit_length+7)//8,byteorder='big'))
    return bytes(bytearray([2,len(dataAsByteArr),sequenceNumber])+dataAsByteArr)    

def makeFINPacket(sequenceNumber): 
    return bytes(bytearray([3,sequenceNumber]))

def unreliableSend(packet, sock, address, errRate):
    if errRate < rd.randint(0,100):
        sock.sendto(packet, address)



#This function returns the accepted client's address.
def listenForHandshake(sock:socket.socket):
    while True:
        data,address=sock.recvfrom(1024)
        packet=bytearray(data)
        if(packet[0]==0):
            filename=packet[2:].decode("utf-8")
            if(filename==serverfilename):
                print("Got the handshake packet from a client.")
                return address
            else:
                continue


def handshakeServer(sock,address):
    
    handshakeACKserver=makeACKPacket(0)
    unreliableSend(handshakeACKserver,sock,address,errorRate)
    print("Sent ACK for handshake packet of the client.")

    while True:
        handshakeACKclient=recieveWithTimeout(sock)
        if(handshakeACKclient!=None):
            print("Got the ACK for handshake from the client.")
            return address

#server'in last sequence number'i file'in last sequence number'i + 1 olmali.
def endingSequenceServer(sock:socket.socket,address,serverLastSequenceNumber:int):
    
    FINServer=makeFINPacket(serverLastSequenceNumber)
    timeoutForEnding=0
    while(timeoutForEnding<5):
        timeoutForEnding+=1
        unreliableSend(FINServer,sock,address,errorRate)
        print("Sent the FIN of the server.")

        packet=recieveWithTimeout(sock)
        if( packet!=None and ( (packet[0]==1 and packet[1]==serverLastSequenceNumber) or (packet[0]==3 and packet[1]==serverLastSequenceNumber+1) ) ):
            FINclientACK=makeACKPacket(serverLastSequenceNumber+1)
            print("Sent the ACK for FIN of the client.")
            unreliableSend(FINclientACK,sock,address,errorRate)
            break
    sock.close()

def packetizeFile(file:str,window_size:int):
    filePackets=[]
    lines=file.split('\n')
    i=0
    for line in lines:
        if(line!=""):
            sequenceNumber=i%(window_size*2)
            packet=makeDATAPacket(bytearray( (line+'\n').encode() ),sequenceNumber)
            #[packet, time passed since last transmission, (-1 untransmitted or 0 not ACK'ed or 1 ACK'ed)]
            filePackets.append([packet,None,-1])
            i+=1
    return filePackets
    


#startTime, beginning of time elapsing until we sent timed out packets.
def sendTimedOutPackets(sock:socket.socket,address,send_base,nextindex,window_size,packets,startTime):
    endTime=time.perf_counter()
    timeElapsed=(endTime-startTime)*1000000
    for i in range(window_size):
        if(i+send_base<len(packets) and i+send_base<nextindex):
            info=packets[i+send_base]
            info[1]+=timeElapsed
            
            if(info[1]>timeoutTime*1000000 and info[2]!=1):
            #Cunku timeoutTime unite'si seconds
            #1000000 ile carparak microseconds'a donusturmus oldum.
                unreliableSend(info[0],sock,address,errorRate)
                info[1]=0
                print(f"Timeout for the packet with sequence number {info[0][2]}, it is sent again.")
            packets[i+send_base]=info


#Ilk defa gondericeksem startTime'larini baslatmam gerekebilir. Kim bilir ne tur bug'larla karsilasicam:(
def sendTheFile(sock:socket.socket,address,window_size:int,filePackets:list):
    
    theArray=filePackets
    sequenceNumberSize=2*window_size
    send_base=0
    nextindex=0

    while True:
        startTime=time.perf_counter()
        
        packet=recieveWithTimeout(sock)

        if(packet!=None and packet[0]==1):
            packetSeqnum=packet[1]
            print(f"Got the ACK for packet with sequence number {packet[1]}")
            indexACK=-1
            if(packetSeqnum>theArray[nextindex-1][0][2]):
                indexACK=(nextindex-1)-((theArray[nextindex-1][0][2]+sequenceNumberSize)-packetSeqnum)

            else:
                indexACK=(nextindex-1)-(theArray[nextindex-1][0][2]-packetSeqnum)

            theArray[indexACK][2]=1
            if(indexACK==send_base):
                send_base+=1
                if(send_base<len(theArray)):
                    packetInfoFromTheArray=theArray[send_base]
                    while(packetInfoFromTheArray[2]==1):
                        send_base+=1
                        if(send_base<len(theArray)):
                            packetInfoFromTheArray=theArray[send_base]
                        else:
                            break
            
            #I should start ending sequence.
            if(send_base==len(theArray) or (indexACK%sequenceNumberSize==theArray[len(theArray)-1][0][2] and nextindex==len(theArray))):
                #theArray[len(theArray)-1][0][1] son paketin sequence number'i
                #nextindex'in theArray length'ine esit olmasi bize sona gelindigini 
                #belirtecek.
                print("Got the ACK for the last remaining packet of the file, let the end begin.")
                endingSequenceServer(sock,address,theArray[len(theArray)-1][0][1]+1)
                break
        

        
        if(nextindex<=send_base+window_size-1 and nextindex<len(theArray)):
            print(f"Sent the packet with sequence number {theArray[nextindex][0][2]}")
            unreliableSend(theArray[nextindex][0],sock,address,errorRate)
            theArray[nextindex][1]=0
            theArray[nextindex][2]=0
            nextindex+=1
        

        
        sendTimedOutPackets(sock,address,send_base,nextindex,window_size,theArray,startTime)



def main():
    global windowSize
    global errorRate
    global serverfilename
    global serverfile

    udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_socket.bind(("127.0.0.1",server_port))

    with open("sorrowful_be_the_heart_penitent_one", "r") as file:
        serverfile = file.read()

    print(f"Server file name is {serverfilename}.")
    
    windowSize=int(input("Enter the window size(It should be same in the client and the server):"))
    errorRate=int(input("Enter the error rate in the channel:"))
    
    address=listenForHandshake(udp_socket)
    address=handshakeServer(udp_socket,address)
    packets=packetizeFile(serverfile,windowSize)
    sendTheFile(udp_socket,address,windowSize,packets)

if __name__ == "__main__":
    main()