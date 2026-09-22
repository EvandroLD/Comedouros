import time

class Reader():
    def __init__(self, ser) -> None:
        """
        RFID reader object
        """
        self.ser = ser

    def clear_serial_buffers(self):
        """
        flush serial data buffers
        """
        self.ser.reset_input_buffer()
        self.ser.reset_output_buffer()


    def read(self) -> str:
        """
        Read from serial interface. 

        return: string hex representation of 16 bit words
        note - if 0xE280 is sent, add E2 and 80 end to end bitwise and that will
        represent the word in MSB first format
        """

        while self.ser.readline() != b'\n':
                time.sleep(0.0001)

        data = self.ser.readline()

        decoded = data.decode()

        return decoded.replace('\r\n', '')
    
    def hex_str_to_int_list(self, input_string:str, reversed:bool=False):
        """
        input_string: a string of hex words in MSB first format. EX: 'E2801160' for a two word string
        reversed: if True, output will be LSB first

        return: words (int) - MSB or LSB first depending on value of 'reversed'
        """
        if len(input_string) >=4:

            hex_list = [input_string[i:i+4] for i in range(0, len(input_string), 4)]

            int_values = list(map(lambda x: (int(x[0:2], 16) << 8) | int(x[2:4], 16), hex_list))
            if reversed:
                return list(map(lambda x: int(bin(x)[2:].zfill(16)[::-1],2), int_values))
            else:
                return list(map(lambda x: int(bin(x)[2:].zfill(16),2), int_values))
        else:
            return False

    def hex_str_to_bin_list(self, input_string, reversed:bool=False):
        """
        input_string: a string of hex words in MSB first format. EX: 'E2801160' for a two word string
        reversed: if True, output will be LSB first

        return: words (int) - MSB or LSB first depending on value of 'reversed'
        """
        if len(input_string) >=4:

            hex_list = [input_string[i:i+4] for i in range(0, len(input_string), 4)]

            int_values = list(map(lambda x: (int(x[0:2], 16) << 8) | int(x[2:4], 16), hex_list))
            if reversed:
                return list(map(lambda x: bin(x)[2:].zfill(16)[::-1], int_values))
            else:
                return list(map(lambda x: bin(x)[2:].zfill(16), int_values))
        else:
            return False

    def convert_to_raw(self, input_int_list):
        """
        converts MSB first int list to single binary string

        input_int_list: MSB first word list

        return: binary string (each word padded to 16 bits) (LSB in element 0)
        """

        output_binary_string = ''
        for i in range(len(input_int_list)):
            output_binary_string += bin(input_int_list[i])[2:].zfill(16)
        return output_binary_string


    def read_TID_bank(self, addr:int=0, words:int=6, raw:bool=False):
        """
        Read lower 96 bytes from TID bank (Bank 2)

        (lower 48 and extended)

        addr: Starting address
        len: Words to read from tag
        raw: Returns the hex string if true

        return: LSB first converted ints (default)
                HEX string if raw is set to True
        """
        to_write = "\nR2,{},{}\r".format(addr,words).encode('utf-8')
        self.ser.write(to_write)

        string_response =  self.read().replace('R', '').encode('utf-8')

        if len(string_response) <= 2:
            return False
        if raw:
            return string_response
        else:
            return self.hex_str_to_int_list(string_response)
        
    def read_EPC_bank(self, words:int=8, raw:bool=False, crc:bool=True):
        """
        Read single tag EPC bank 
        Returned data from the reader is CRC16+PC+EPC

        words: number of words to read from EPC bank

        raw: if True, the raw hex string from the reader will be returned

        return: LSB first converted ints (default)
                HEX string if raw is set to True
        """
        to_write = "\nR1,0,{}\r".format(words).encode('utf-8')
        self.ser.write(to_write)

        string_response_bytes =  self.read().replace('R', '').encode('utf-8')


        if len(string_response_bytes) <= 2:
            return False
        

        if crc:

            string_form = str(string_response_bytes)

            crc_from_tag = int(string_form[2:6], 16)

            pc_and_epc_string = string_form[6:-1]

            input_bytes = bytes.fromhex(pc_and_epc_string)

            crc_calculated = self.crc16(input_bytes)
            if crc_calculated == crc_from_tag:

                if raw:
                    return string_response_bytes
                else:
                    return self.hex_str_to_int_list(string_response_bytes)
            else:

                return False
        else:
            if raw:
                return string_response_bytes
            else:
                return self.hex_str_to_int_list(string_response_bytes)
        
    def multi_tag_EPC_read(self, raw=False, crc=True, max=4, timeout=2):
        """
        Read EPC of multiple tags

        raw: if true, the output will be the raw PC+EPC+CRC16 data
        
        crc: if true, the crc will be checked before returning the EPC data split into words.
            the calculated and read crc will be returned along with the data 

        Note: For some reason, the reader outputs the data differently compared to single EPC read.
            Here, the output format is PC+EPC+CRC16
        """
        to_write = "\nU{}\r".format(max).encode('utf-8')
        self.ser.write(to_write)

        data = []
        inicio_leitura = time.monotonic()
        while True:

            if time.monotonic() - inicio_leitura >= timeout:
                print("Tempo esgotado aguardando resposta do leitor RFID.")
                return data if data else False

            linha = self.ser.readline()
            if not linha or linha in {b'\n', b'\r\n'}:
                continue

            string_response_bytes = linha
            if string_response_bytes.strip() in {b'U', b'U\r'}:
                break

            string_form = str(string_response_bytes)

            if crc:

                try:
                    crc_from_tag = int(string_form[-9:-5], 16)
                    pc_and_epc_string = string_form[3:-9]
                    input_bytes = bytes.fromhex(pc_and_epc_string)
                except (ValueError, IndexError):
                    print(f"Resposta RFID invalida: {string_response_bytes!r}")
                    continue

                crc_calculated = self.crc16(input_bytes)

                if crc_calculated == crc_from_tag:
                    print("CRC good")
                    formatted = string_form[-9:-5]+string_form[3:-9] 
                    if raw:
                        data.append([formatted, crc_from_tag, crc_calculated])
                    else:
                        data.append([self.hex_str_to_int_list(formatted), crc_from_tag, crc_calculated])
                else:
                    print("CRC bad")
            else:
                formatted = string_form[-9:-5]+string_form[3:-9] 
                if raw:
                    data.append(formatted)
                else:
                    data.append(self.hex_str_to_int_list(formatted))
        if len(data) == 0: return False
        return data


    def multi_tag_general_read(self, raw=True):
        """
        Read the EPC and other data of multiple tags using the "UR" command
        """
        return True

    def reader_ID(self):
        """
        Return the reader ID
        """
        self.ser.write(b'\nS\r')
        return self.read()
    
    def crc16(self, data: bytes) -> int:
        """
        Calculate ISO/IEC 13239 CRC

        Defined by:
        initial CRC: 0xFFFF
        reflect input: False
        polynomial: 0x1021 (X^16+X^12+X^5+1)
        reflect output: False
        XOR output: 0xFFFF
        """
        poly = 0x1021
        crc = 0xFFFF

        for byte in data:
            crc ^= byte << 8
            for _ in range(8):
                if (crc & 0x8000):
                    crc = (crc << 1) ^ poly
                else:
                    crc = crc << 1
                
                crc &= 0xFFFF

        return crc ^ 0xFFFF
    
    def set_tx_power_level(self, pwr_level:int) -> bool:
        """
        Set the transmit power level
        """
        hex_power_level = hex(pwr_level+2)[2:].zfill(2).upper()
        to_write = "\nN1,{}\r".format(hex_power_level).encode('utf-8')
        self.ser.write(to_write)
        while self.ser.readline() != b'\n':
                time.sleep(0.0001)
        ticks = 0
        while self.ser.readline().decode("utf-8")[1:3] != hex_power_level:
            time.sleep(0.001)
            timeout += 1
            if ticks == 500:
                return False
        return True
    
    def write_user_memory(self, start_address: int, data_words: list) -> bool:
        """
        Grava dados no USER bank (Bank 3)
        """
        for i, word in enumerate(data_words):
            word_hex = f"{word:04X}" 
            cmd = f"\nW3,{start_address + i},{word_hex}\r".encode("utf-8")
            print(f"Enviando comando: {cmd.decode().strip()}")
            self.ser.write(cmd)

            while True:
                linha = self.ser.readline()
                if not linha:
                    break
                linha_decod = linha.decode().strip()
                if linha_decod: 
                    print(f"Resposta: '{linha_decod}'")
                    if linha_decod == "X":
                        print(f" Falha ao gravar palavra {i}: {linha_decod}")
                        return False
                    if linha_decod == f"W3,{start_address + i},{word_hex}":
                        break
        return True

