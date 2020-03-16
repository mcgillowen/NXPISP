from . import ISPChip
from time import sleep
from timeout_decorator import TimeoutError, timeout
import zlib
import typing

NXPReturnCodes = {
        "CMD_SUCCESS"                               : 0x0,
        "INVALID_COMMAND"                           : 0x1,
        "SRC_ADDR_ERROR"                            : 0x2,
        "DST_ADDR_ERROR"                            : 0x3,
        "SRC_ADDR_NOT_MAPPED"                       : 0x4,
        "DST_ADDR_NOT_MAPPED"                       : 0x5,
        "COUNT_ERROR"                               : 0x6,
        "INVALID_SECTOR/INVALID_PAGE"               : 0x7,
        "SECTOR_NOT_BLANK"                          : 0x8,
        "SECTOR_NOT_PREPARED_FOR_WRITE_OPERATION"   : 0x9,
        "COMPARE_ERROR"                             : 0xa,
        "BUSY"                                      : 0xb,
        "PARAM_ERROR"                               : 0xc,
        "ADDR_ERROR"                                : 0xd,
        "ADDR_NOT_MAPPED"                           : 0xe,
        "CMD_LOCKED"                                : 0xf,
        "INVALID_CODE"                              : 0x10,
        "INVALID_BAUD_RATE"                         : 0x11,
        "INVALID_STOP_BIT"                          : 0x12,
        "CODE_READ_PROTECTION_ENABLED"              : 0x13,
        "Unused 1"                                  : 0x14,
        "USER_CODE_CHECKSUM"                        : 0x15,
        "Unused 2"                                  : 0x16,
        "EFRO_NO_POWER"                             : 0x17,
        "FLASH_NO_POWER"                            : 0x18,
        "Unused 3"                                  : 0x19,
        "Unused 4"                                  : 0x1a,
        "FLASH_NO_CLOCK"                            : 0x1b,
        "REINVOKE_ISP_CONFIG"                       : 0x1c,
        "NO_VALID_IMAGE"                            : 0x1d,
        "FAIM_NO_POWER"                             : 0x1e,
        "FAIM_NO_CLOCK"                             : 0x1f,
        "NoStatusResponse"                          : 0xff,
    }

class NXPChip(ISPChip):
    kWordSize = 4
    kPageSizeBytes = 64
    SectorSizePages = 16
    MaxByteTransfer = 1024
    StatusRespLength = len(ISPChip.kNewLine) + 1
    Parity = None
    DataBits = 8
    StopBits = 1
    SyncString = "Synchronized"+ISPChip.kNewLine
    SyncVerified = "OK"+ISPChip.kNewLine
    ReturnCodes = NXPReturnCodes
    CRCLocation = 0x000002fc

    CRCValues = {
        "NO_ISP": 0x4e697370,
        "CRP1" : 0x12345678,
        "CRP2" : 0x87654321,
        "CRP3" : 0x43218765,
    }

    @classmethod
    def GetErrorCodeName(cls, code : int) -> str:
        code = int(code)
        for item in cls.ReturnCodes.items():
            if code == item[1]:
                return item[0]
        return "Not Found"

    def GetReturnCode(self) -> int:
        for i in range(10):
            #sleep(.1)
            try:
                resp = self.ReadLine().strip()
                return int(resp)
            except ValueError:
                pass
        return self.ReturnCodes["NoStatusResponse"]

    def RaiseReturnCodeError(self, code : int, call_name : str) -> None:
        if(int(code) != self.ReturnCodes["CMD_SUCCESS"]):
            raise UserWarning("Return Code Failure in {} {} {}".format(call_name, self.GetErrorCodeName(code), code))

    def AssertReturnCode(self, call_name : str) -> None:
        '''
        Get a return code with no response
        '''
        code = self.GetReturnCode()
        self.RaiseReturnCodeError(code, call_name)

    def Write(self, string) -> None:
        if type(string) != bytes:
            out = bytes(string, encoding = "utf-8")
        else:
            out = string
        #print(out)
        self.WriteSerial(out)
        #self.WriteSerial(bytes(self.kNewLine, encoding = "utf-8"))

    '''
    Takes the command string, return the response code
    '''
    def WriteCommand(self, command_string) -> int:
       self.Write(command_string)
       self.Write(self.kNewLine)
       return self.GetReturnCode()

    def Unlock(self):
        '''
        Enables Flash Write, Erase, & Go
        '''
        self.ClearBuffer()
        response_code = self.WriteCommand("U 23130")
        self.RaiseReturnCodeError(response_code, "Unlock")

    def SetBaudRate(self, baudRate, stopBits = 1):
        '''
        Baud Depends of FAIM config, stopbit is 1 or 2
        '''
        response_code = self.WriteCommand("B {} {}".format(baudRate, stopBits))
        self.RaiseReturnCodeError(response_code, "Set Baudrate")

    def Echo(self, on : bool = True):
        '''
        ISP echos host when enabled
        '''
        if on:
            command = "A 1"
        else:
            command = "A 0"
        response_code = self.WriteCommand(command)
        self.RaiseReturnCodeError(response_code, "Set Echo")

    def WriteToRam(self, StartLoc : int , Data : bytes):
        assert(len(Data)%self.kWordSize == 0)
        assert(StartLoc+len(Data) < self.RAMRange[1] and StartLoc >= self.RAMRange[0])

        print("Write to RAM %d bytes"%len(Data))
        #while i < len(Data):
        #    self.Write("W %d %d"%(StartLoc + i, kWordSize))
        #    self.AssertReturnCode("Write to RAM")#get confirmation
        #    self.Write(Data[i:i+kWordSize])#Stream data after confirmation
        #    i+=kWordSize

        #when transfer is complete the handler sends OK<CR><LF>
        response_code = self.WriteCommand("W %d %d"%(StartLoc, len(Data)))
        self.RaiseReturnCodeError(response_code, "Write to RAM")
        self.Write(Data)#Stream data after confirmation
        #self.Write("OK"+self.kNewLine)
        try:
            print(self.ReadLine())
        except TimeoutError:
            return

    @timeout(4)
    def ReadMemory(self, StartLoc : int, num_bytes : int):
        assert(num_bytes%self.kWordSize == 0)
        #assert(StartLoc+num_bytes < self.RAMRange[1] and StartLoc >= self.RAMRange[0])
        print("ReadMemory")

        #self.Flush()
        #self.Read()
        #self.ClearBuffer()
        #self.Flush()

        print("R %d %d"%(StartLoc, num_bytes))
        response_code = self.WriteCommand("R %d %d"%(StartLoc, num_bytes))
        self.RaiseReturnCodeError(response_code, "Read Memory")

        while(len(self.DataBufferIn) < (num_bytes)):
            self.Read()
        # Command success is sent at the end of the transfe
        # Command success is sent at the end of the transferr
        data = []
        while(len(self.DataBufferIn)):
            ch = self.DataBufferIn.popleft()
            data.append(ch)

        if(len(data) != num_bytes):
            print(data, len(data), num_bytes)
        assert(len(data) == num_bytes)
        return bytes(data)

    def PrepSectorsForWrite(self, StartSector : int, EndSector : int):
        try:
            response_code = self.WriteCommand("P %d %d"%(StartSector, EndSector))
            self.RaiseReturnCodeError(response_code, "Prep Sectors")
        except:
            response_code = self.WriteCommand("P %d %d"%(StartSector, EndSector))
            self.RaiseReturnCodeError(response_code, "Prep Sectors")

    def CopyRAMToFlash(self, FlashAddress : int, RAMAddress : int, num_bytes : int):
        assert(RAMAddress+num_bytes < self.RAMRange[1] and RAMAddress >= self.RAMRange[0])
        assert(FlashAddress + num_bytes < self.FlashRange[1] and FlashAddress >= self.FlashRange[0])

        assert(FlashAddress%self.kPageSizeBytes == 0)
        assert(RAMAddress%self.kWordSize == 0)

        response_code = self.WriteCommand("C %d %d %d"%(FlashAddress, RAMAddress, num_bytes))
        self.RaiseReturnCodeError(response_code, "Copy RAM To Flash")
        #sleep(.2)

    def Go(self, Address : bool, ThumbMode : bool = False):
        '''
        Start executing code at the specified spot
        '''
        mode = ""
        if ThumbMode:
            mode = 'T'
        response_code = self.WriteCommand("G %d %s"%(Address, mode))
        self.RaiseReturnCodeError(response_code, "Go")

    def EraseSector(self, StartSector : int, EndSector : int):
        response_code = self.WriteCommand("E %d %d"%(StartSector, EndSector))
        self.RaiseReturnCodeError(response_code, "Erase Sectors")

    def ErasePages(self, StartPage : int, ErasePage : int):
        response_code = self.WriteCommand("X %d %d"%(StartPage, EndPage))
        self.RaiseReturnCodeError(response_code, "Erase Pages")

    def CheckSectorsBlank(self, StartSector : int, EndSector : int) -> bool:
        assert(StartSector <= EndSector)
        response_code = self.WriteCommand("I %d %d"%(StartSector, EndSector) + self.kNewLine)
        try:
            self.ReadLine()
            response = self.ReadLine().strip()
            print("Check Sectors Blank response", response)
        except TimeoutError:
            pass
        if response_code == NXPReturnCodes["CMD_SUCCESS"]:
            return True
        elif response_code == NXPReturnCodes["SECTOR_NOT_BLANK"]:
            return False

        self.RaiseReturnCodeError(response_code, "Blank Check Sectors")

    def ReadPartID(self):
        response_code = self.WriteCommand("J")
        self.RaiseReturnCodeError(response_code, "Read Part ID")
        resp = self.ReadLine()
        return int(resp)

    def ReadBootCodeVersion(self):
        '''
        LPC84x sends a 0x1a first for some reason. Also the boot version seems to be Minor then Major not like the docs say
        '''
        response_code = self.WriteCommand("K")
        self.RaiseReturnCodeError(response_code, "Read Bootcode Version")
        Minor = self.ReadLine().strip()
        Major = self.ReadLine().strip()
        return "%d.%d"%(int(Major), int(Minor))


    '''
    Checks to see if two sections in the memory map are equal
    '''
    def MemoryLocationsEqual(self, Address1 : int, Address2 : int, num_bytes : int):
        self.Write("M %d %d %d"%(Address1, Address2, num_bytes) + self.kNewLine)
        response = self.ReadLine()
        response_code = int(response[0])
        if response_code == NXPReturnCodes["CMD_SUCCESS"]:
            return True
        elif response_code == NXPReturnCodes["COMPARE_ERROR"]:
            # offset of first mismatch
            print("Memory locations not equal", bytes(response, encoding = "utf-8"))
            return False
        self.RaiseReturnCodeError(response_code, "Compare")

    def ReadUID(self):
        response_code = self.WriteCommand("N")
        self.RaiseReturnCodeError(response_code, "Read UID")
        UID0 = self.ReadLine().strip()
        UID1 = self.ReadLine().strip()
        UID2 = self.ReadLine().strip()
        UID3 = self.ReadLine().strip()
        return " ".join(["0x%08x"%int(uid) for uid in [UID0, UID1, UID2, UID3]])

    def ReadCRC(self, Address, num_bytes : int) -> int:
        try:
            response_code = self.WriteCommand("S %d %d"%(Address, num_bytes))
        except TimeoutError:
            response_code = self.WriteCommand("S %d %d"%(Address, num_bytes))

        self.RaiseReturnCodeError(response_code, "Read CRC")
        return int(self.ReadLine().strip())

    def ReadFlashSig(self, StartAddress : int, EndAddress : int, WaitStates : int = 2, Mode : int = 0):
        assert(StartAddress < EndAddress)
        assert(StartAddress >= self.FlashRange[0])
        assert(EndAddress <= self.FlashRange[1])
        response_code = self.WriteCommand("Z %d %d %d %d"%(StartAddress, EndAddress, WaitStates, Mode))
        self.RaiseReturnCodeError(response_code, "Read Flash Signature")
        return self.ReadLine()

    def ReadWriteFAIM(self):
        response_code = self.WriteCommand("O")
        self.RaiseReturnCodeError(response_code, "Read Write FAIM")

    def ResetSerialConnection(self):
        self.Flush()
        self.Write(self.kNewLine)
        try:
            pass
            self.ReadLine()
        except TimeoutError:
            pass

    def InitConnection(self):
        #self.ResetSerialConnection()
        try:
            try:
                self.SyncConnection()
                self.SetCrystalFrequency(self.CrystalFrequency)
            except (UserWarning, TimeoutError) as w:
                print("Sync Failed", w)
                print("Connect to running ISP")
                self.ClearSerialConnection()
            self.Echo(False)
            try:
                self.ReadLine()
                self.Flush()
                self.ClearBuffer()
            except TimeoutError:
                pass
            self.CheckPartType()
            uid = self.ReadUID()
            print("Part UID: %s"%uid)
            bootCodeVersion = self.ReadBootCodeVersion()
            print("Boot Code Version: %s"%bootCodeVersion)
            self.SetBaudRate(self.BaudRate)
            print("Baudrate set to %d"%self.BaudRate)
        except Exception as e:
            print(e, type(e))
            raise

    def SyncConnection(self):
        synced = False
        self.ClearSerialConnection()
        self.Flush()
        for i in range(5):
            self.Write('?'*15)
            #self.Write('?' + self.kNewLine)
            try:
                FrameIn = self.ReadLine()
                if(self.SyncString.strip() in FrameIn.strip()):
                    synced = True
                    break
            except TimeoutError:
                pass

        if(not synced):
            #Check for SyncString
            raise UserWarning("Syncronization Failure")

        #self.Flush()
        self.Write(self.SyncString)#echo SyncString
        try:
            FrameIn = self.ReadLine()#discard echo
        except TimeoutError:
            pass

        verified = False
        for i in range(3):
            try:
                FrameIn = self.ReadLine()#Should be OK\r\n
                if(self.SyncVerified.strip() in FrameIn):
                    verified = True
                    break
            except TimeoutError:
                pass
        if not verified:
            raise UserWarning("Verification Failure")
        print("Syncronization Successful")

    def ClearSerialConnection(self):
        self.Write(self.kNewLine)
        self.ClearBuffer()
        self.Flush()
        self.Read()
        self.ClearBuffer()
        self.Flush()
        for i in range(2):
            try:
                self.ReadLine()
            except TimeoutError:
                pass

    def SetCrystalFrequency(self, frequency_khz : int):
        self.Write("%d"%frequency_khz + self.kNewLine)
        verified = False
        for i in range(3):
            try:
                FrameIn = self.ReadLine()#Should be OK\r\n
                if(self.SyncVerified.strip() in FrameIn):
                    verified = True
                    break
            except TimeoutError:
                pass
        if not verified:
            raise UserWarning("Verification Failure")


    def CheckPartType(self):
        PartID = self.ReadPartID()
        if(PartID not in self.PartIDs):
            raise UserWarning("%s recieved 0x%08x"%(self.ChipName, PartID))
        print("Part Check Successful, 0x%08x"%(PartID))

    def CheckFlashWrite(Data, FlashAddress : int):
        '''
        Read Memory and compare it to what was written
        '''

        DataRead = self.ReadMemory(FlashAddress, len(Data))

        assert(len(Data) == len(DataRead))
        assert(type(Data) == type(DataRead))
        if(Data != DataRead):
            return False
        return True

    def WriteFlashSector(self, sector : int, Data : bytes):
        RAMAddress = self.RAMStartWrite
        sectorSizeBytes = self.kPageSizeBytes*self.SectorSizePages
        FlashAddress = self.FlashRange[0] + sector*sectorSizeBytes
        print("Writing Sector: %d\nFlash Address: %x\nRAM Address: %x\n"%(sector, FlashAddress, RAMAddress))

        assert(len(Data) == sectorSizeBytes)
        #Data += bytes(sectorSizeBytes - len(Data))

        data_crc = zlib.crc32(Data, 0)
        sleep(.1)
        try:
            ram_crc = self.ReadCRC(RAMAddress, num_bytes = len(Data))
        except:
            ram_crc = self.ReadCRC(RAMAddress, num_bytes = len(Data))
        while(ram_crc != data_crc):
            sleep(.1)
            self.WriteToRam(RAMAddress, Data)
            sleep(.1)
            ram_crc = self.ReadCRC(RAMAddress, num_bytes = len(Data))
            if(data_crc != ram_crc):
                print("CRC Check failed", data_crc, ram_crc)
        assert(data_crc == ram_crc)

        print("Prep Sector")
        assert(self.CheckSectorsBlank(sector, sector))
        sleep(.1)
        self.PrepSectorsForWrite(sector, sector)
        sleep(.1)
        print("Write to Flash")
        self.CopyRAMToFlash(FlashAddress, RAMAddress, sectorSizeBytes)
        sleep(.1)
        flash_crc = self.ReadCRC(FlashAddress, num_bytes = len(Data))
        assert(flash_crc == data_crc)
        assert(self.MemoryLocationsEqual(FlashAddress, RAMAddress, sectorSizeBytes))

    def WriteImage(self, ImageFile : str):
        self.Unlock()
        sector = 0
        writeCount = 0

        SectorBytes = self.SectorSizePages*self.kPageSizeBytes
        assert(SectorBytes%self.kWordSize == 0)

        with open(ImageFile, 'rb') as f:
            prog = f.read()
            image = MakeBootable(self.kCheckSumLocation, prog)
            print("Program Length:", len(prog))
            while(True):
                print("Sector", sector)
                DataChunk = image[writeCount : writeCount + SectorBytes]
                if(not len(DataChunk)):
                    break
                elif(len(DataChunk) != SectorBytes):
                    DataChunk += bytes([0xff] *(SectorBytes - len(DataChunk)))
                assert(sector < self.SectorCount)
                self.PrepSectorsForWrite(sector, sector)
                sleep(.1)
                self.EraseSector(sector, sector)
                sleep(.1)
                assert(self.CheckSectorsBlank(sector, sector))
                sleep(.1)

                print("Write Flash")
                self.PrepSectorsForWrite(sector, sector)
                sleep(.1)
                self.WriteFlashSector(sector, DataChunk)
                sleep(.1)
                #assert(self.ReadSector(sector) == DataChunk)
                print("Flash Written")

                writeCount += SectorBytes
                sector += 1
            #write the cpu exception vector

        chip_flash_sig = self.ReadFlashSig(self.FlashRange[0], self.FlashRange[1])
        print("Flash Signature: %s"%chip_flash_sig)
        print("Programming Complete.")

    def FindFirstBlankSector(self) -> int:
        for sector in range(self.SectorCount):
            if self.CheckSectorsBlank(sector, self.SectorCount - 1):
                return sector
        return self.SectorCount - 1

    def ReadSector(self, sector : int) -> bytes:
        SectorBytes = self.SectorSizePages*self.kPageSizeBytes
        assert(SectorBytes%self.kWordSize == 0)
        return self.ReadMemory(sector*SectorBytes, SectorBytes)

    def ReadImage(self, ImageFile : str):
        blank_sector = self.FindFirstBlankSector()
        with open(ImageFile, 'wb') as f:
            for sector in range(blank_sector):
                print("Sector ", sector)
                f.write(self.ReadSector(sector))

    def MassErase(self):
        kSectorEnd = self.SectorCount - 1
        sleep(1)
        self.ClearBuffer()
        self.Unlock()
        self.PrepSectorsForWrite(0, kSectorEnd)
        self.EraseSector(0, kSectorEnd)
        print("Checking Sectors are blank")
        assert(self.CheckSectorsBlank(0, kSectorEnd))

def MakeBootable(vector_table_loc, orig_image):
    #Calculate 2's compliment of the checksum
    #of table entries 0 to 6
    import struct
    u32_mod = (1<<32)
    # make this a valid image by inserting a checksum in the correct place

    #kTableEntriesChecked = 6
    #table = image[vector_table_loc - kTableEntriesChecked : vector_table_loc]
    # <8I is littl endian, 8 bits, as 32 bit integers
    intvecs = struct.unpack("<8I", orig_image[0:32])
    # default vector is 5: 0x14, new cortex cpus use 7: 0x1c
    valid_image_csum_vec = 7
    # calculate the checksum over the interrupt vectors
    csum = 0
    intvecs_list = []
    for vec in range(0, len(intvecs)):
        intvecs_list.append(intvecs[vec])
        if valid_image_csum_vec == 5 or vec <= valid_image_csum_vec:
            csum = csum + intvecs[vec]
    # remove the value at the checksum location
    csum -= intvecs[valid_image_csum_vec]
    csum %= u32_mod
    csum = u32_mod - csum

    print("Inserting intvec checksum 0x%08x in image at offset %d" %
            (csum, valid_image_csum_vec))

    intvecs_list[valid_image_csum_vec] = csum

    image = b''
    for vecval in intvecs_list:
        image += struct.pack("<I", vecval)

    image += orig_image[32:]
    return image

