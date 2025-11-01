import socket
import random as rd
import select 
import time 


server_ip = "127.0.0.1"
server_port = 10001
client_port = 10000
serverfilename="sorrowful_be_the_heart_penitent_one"
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





#If handshake is failed, it will return None, if it succeeds, returns segment0
def handshakeClient(sock,filename):
    #After 5 timeouts, it will give up. We may enter the file name wrong after all. 
    timeoutNumber=0

    while(timeoutNumber<5):
        packet=makeHandshakePacket(filename)
        unreliableSend(packet,sock,(server_ip,server_port),errorRate)
        print("Handshake packet was sent.")
        serverACK=recieveWithTimeout(sock)
        if(serverACK==None):
            timeoutNumber+=1
            continue
        print("ACK from server for handshake came.")

        #Client says "Okay send it." . It may get lost. As a response we should get the segment 0
        unreliableSend(serverACK,sock,(server_ip,server_port),errorRate)
        print("Same ACK packet was sent to the server, by the client ")
        segment0=None
        while(segment0==None):
            unreliableSend(serverACK,sock,(server_ip,server_port),errorRate)
            segment0=recieveWithTimeout(sock)
        
        return segment0

    return None


#Hata cikti burada, sadece str degil tuple istiyor.
def unreliableSend(packet, sock, address, errRate):
    if errRate < rd.randint(0,100):
        sock.sendto(packet, address)



def endingSequenceClient(sock:socket.socket,serverFIN:bytearray):
    serverLastSeqeunceNumber=serverFIN[1]
    
    FINServer_ACK=makeACKPacket(serverLastSeqeunceNumber)
    FINClient=makeFINPacket(serverLastSeqeunceNumber+1)
    timeoutForEnding=0
    while(timeoutForEnding<5):
        timeoutForEnding+=1
        unreliableSend(FINServer_ACK,sock,(server_ip,server_port),errorRate)
        unreliableSend(FINClient,sock,(server_ip,server_port),errorRate)
        print("Sent ACK for FIN of the server.")
        print("Sent FIN of the client.")
        packet=recieveWithTimeout(sock)
        if(packet!=None and packet[0]==1 and packet[1]==FINClient[1]):
            print("Got the ACK for FIN of the client.")
            break
    

    sock.close()

def getTheFile(sock:socket.socket,window_size:int,filename:str):

    #buffer'in size'i sequence number size'ina esit.
    bufferSize=window_size*2
    buffer=[None]*(bufferSize)
    rcv_base=0

    segment0=handshakeClient(sock,filename)

    if(segment0!=None):
        print(f"Client got the packet with sequence number {segment0[2]}")
        file=""        
        
        #rcv_base ve segment0'in sequence number'i 0 olmasi gerekiyor bu kisimda.
        #Burada segment0'i buffer'dan upper layer'a atmis oluyoruz, yani
        #client'taki olusmakta olan file'a data'yi eklemis oluyoruz.
        buffer[segment0[2]]=segment0
        filePiece=segment0[3:]
        file+=filePiece.decode("utf-8")
        buffer[rcv_base]=None
        rcv_base+=1
        rcv_base=rcv_base%bufferSize

        while(True):
            packet=recieveWithTimeout(sock)

            if(packet!=None):
                #What kind of packet did we get here?
                #At this point in the program, it can be only DATA or FIN packet.

                #It is a DATA packet.
                if(packet[0]==2):
                    #Already ACK'ed can ACK'ed again.
                    if( ( rcv_base-window_size<=packet[2] and packet[2]<=rcv_base-1 ) or ( rcv_base-window_size<0  and  ( (0<=packet[2] and packet[2]<=rcv_base-1)  or ((rcv_base-window_size)%bufferSize<=packet[2] and packet[2]<bufferSize) ))):
                        dataACK=makeACKPacket(packet[2])
                        print(f"Client already sent ACK for packet with sequence number {packet[2]}, nevertheless it is sent again now.")
                        unreliableSend(dataACK,sock,(server_ip,server_port),errorRate)

                    
                    elif( (rcv_base<=packet[2] and packet[2]<=rcv_base+window_size-1)  or ( rcv_base+window_size-1>=bufferSize and ((0<=packet[2] and packet[2]<(packet[2]<=rcv_base+window_size-1)%bufferSize) or (rcv_base<=packet[2] and packet[2]<bufferSize) )) ):
                        buffer[packet[2]]=packet
                        print(f"Got the packet with sequence number {packet[2]}")
                        dataACK=makeACKPacket(packet[2])
                        unreliableSend(dataACK,sock,(server_ip,server_port),errorRate)
                        print(f"Sent ACK for the packet with sequence number {packet[2]}")

                        #if sequence number equals rcv_base, we can send some packets to upper layers.
                        if(packet[2]==rcv_base):
                            packetFromBuffer=buffer[rcv_base]
                            filePiece=packetFromBuffer[3:]
                            file+=filePiece.decode("utf-8")
                            buffer[rcv_base]=None
                            rcv_base+=1
                            rcv_base=rcv_base%bufferSize
                            packetFromBuffer=buffer[rcv_base]

                            while(packetFromBuffer!=None):
                                filePiece=packetFromBuffer[3:]
                                file+=filePiece.decode("utf-8")
                                buffer[rcv_base]=None
                                rcv_base+=1
                                rcv_base=rcv_base%bufferSize
                                packetFromBuffer=buffer[rcv_base]

                elif(packet[0]==3):
                    #It is a FIN packet.
                    print("Got the FIN packet, the beginning of the end...")
                    endingSequenceClient(sock,packet)
                    break

            else:
                #There is a timeout, packet must be lost on the way.
                continue

        return file             

    else:
        return None



def main():

    global windowSize
    global errorRate

    udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_socket.bind(("127.0.0.1",client_port))

    #filename="sorrowful_be_the_heart_penitent_one"
    
    filename=input("Enter the file name to fetch from server:")
    windowSize=int(input("Enter the window size(It should be same in the client and the server):"))
    errorRate=int(input("Enter the error rate in the channel:"))


    theBeginning=time.perf_counter()
    file=getTheFile(udp_socket,windowSize,filename)
    theEnd=time.perf_counter()
    if(file!=None):
        print("")
        print("Here is the file client wanted:")
        print(file)
        print(f"With {errorRate}% error rate and {windowSize} window size, client took {1000*(theEnd-theBeginning):0.3f} milliseconds to fetch the file from server. ")
        
        with open("clientfile.txt", "w") as newfile:
            newfile.write(file)
        
    else:
        print("File name can be wrong.")
        print("The file you requested couldn't be fetched.")

if __name__ == "__main__":
    main()
