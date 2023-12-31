import shutil
import os
import csv
import re

def read_data_file(file_path):
    file = open(file_path,'rb')
    buffer = file.read()
    file.close()
    return bytearray(buffer)

def write_data_file(buffer,file_path):
    file = open(file_path,'wb')
    file.write(buffer)
    file.close()

def read_freq(file, offset):
    file.seek(offset)
    data = file.read(4)
    hex_data = ''.join(f'{byte:02X}' for byte in reversed(data))   
    return int(hex_data)*10

def freq_to_hex(frequency):
    hex_string = str(int(frequency/10))
    if len(hex_string) % 2 != 0:
        hex_string = '0' + hex_string  # Add a leading '0' if the length is odd
    data = bytes.fromhex(hex_string)[::-1]  # Convert hex string to bytes and reverse the order
    return data

def code_to_hex(code):
    if code is None:
        return bytearray((0xFF,0xFF))
    hex_string = str(code).replace('.','')
    if (hex_string[0]=='D'):
        hex_string = ('8' if (hex_string[4]=='N') else 'C') + hex_string[1:4]
        data = bytes.fromhex(hex_string)[::-1]  # Convert hex string to bytes and reverse the order
        return data        
    else:
        hex_string = hex_string.rjust(4,'0')
        data = bytes.fromhex(hex_string)[::-1]  # Convert hex string to bytes and reverse the order
        return data
        
#TX1 TX2 TX3 TX4 RX1 RX2 RX3 RX4 ?? RXCODE1 RXCODE2 TXCODE1 TXCODE2 06 11 00

def channel_offset(channel):
    real_channel = channel + 2
    page = int(real_channel / 255)
    offset = offsets['channel_data'] + (real_channel+page) * lengths['channel_data']
    return offset

def name_offset(channel):
    real_channel = channel -1
    page = int(real_channel / 372)
    offset = offsets['channel_name'] + real_channel * lengths['channel_name'] + page * 4
    return offset

def write_channel(buffer,channel,name,freq_rx,freq_tx,code_tx,code_rx,isNarrowBw,isLowPwr):
    offset = channel_offset(channel)
    hf = freq_to_hex(freq_rx)
    mode_byte = ((int(not isNarrowBw) << 2) | (int(not isLowPwr) <<1)).to_bytes(length=1,byteorder='little')
    hex_data = freq_to_hex(freq_rx) + freq_to_hex(freq_tx) + b'\xFF' \
        + code_to_hex(code_tx) + code_to_hex(code_rx) + mode_byte + bytearray(b'\x11\x00')
    buffer[offset:offset+len(hex_data)] = hex_data
    write_name(buffer,channel,name)

def string_to_sequence(input_string):
    truncated_string = input_string[:6]  # Take at most 6 characters from the string
    encoded_string = truncated_string.encode('utf-8')  # Encode the string to bytes
    byte_array = bytearray(11)  # Create a 11-byte bytearray
    byte_array[:len(encoded_string)] = encoded_string  # Add the encoded string to the bytearray
    byte_array[10]=0xff
    return byte_array

def write_name(buffer,channel,name):
    offset = name_offset(channel)
    hex_data = string_to_sequence(name)
    buffer[offset:offset+len(hex_data)] = hex_data

def ik2ane_row_filter(row):
    return False if re.search("^(R|RU)",row['(N)ome']) and \
        re.search("^[A-Z][A-Z]$",row['(P)rov.']) and \
        "lombardia" in row['regione'] \
        else True

def ik2ane_process(row):
    row['(N)ome']=row['(P)rov.']+row['(N)ome']
    return row

def chirp_row_filter(row):
    return False;

def ik2ane_csv_read(file_path):
    source_rows = []
    with(open(file_path)) as csvfile:
        reader = csv.DictReader(csvfile,delimiter=';')
        for row in reader:
            source_rows.append(ik2ane_process(row)) if not(ik2ane_row_filter(row)) else None
    source_rows = sorted(source_rows, key=lambda x: x['(N)ome'])
    return source_rows

def chirp_csv_read(file_path):
    source_rows = []
    with(open(file_path)) as csvfile:
        reader = csv.DictReader(csvfile,delimiter=',')
        for row in reader:
            source_rows.append(row) if not(chirp_row_filter(row)) else None
    return source_rows

def chirp_csv_extract(source):
    for row in source:
        freq_rx = float(row['Frequency'])*1e6
        if row['Duplex']=='+':
            freq_tx = freq_rx + float(row['Offset'])*1e6
        elif row['Duplex']=='-':
            freq_tx = freq_rx - float(row['Offset'])*1e6
        else:
            freq_tx=freq_rx

        name = row['Name']
        
        if row['Tone'] == 'DTCS':
            tone_rx = 'D' + row['RxDtcsCode'] + 'N' if row['DtcsPolarity'] == 'NN' else 'I'
        elif row['Tone'] == 'TSQL':
            tone_rx = row['rToneFreq']
        else:
            tone_rx = None

        if row['Tone'] == 'DTCS':
            tone_tx = 'D' + row['DtcsCode'] + 'N' if row['DtcsPolarity'] == 'NN' else 'I'
        elif row['Tone'] == 'TSQL':
            tone_tx = row['cToneFreq']
        else:
            tone_tx = None

        isNarrowBw = True if row['Mode'] == 'NFM' else False
        isLowPower = True if float(row['Power'][:-1]) < 5 else False
        yield (name,freq_rx,freq_tx,tone_rx,tone_tx,isNarrowBw,isLowPower)

def chirp_csv_read(file_path):
    source_rows = []
    with(open(file_path)) as csvfile:
        reader = csv.DictReader(csvfile,delimiter=',')
        for row in reader:
            source_rows.append(row) if not(chirp_row_filter(row)) else None
    return source_rows

def ik2ane_csv_extract(source):
    for row in source:
        freq_rx = row['(F)req'].replace('.','')
        freq_rx = float(freq_rx.replace(',','.'))*1e3
        shift = re.match("([+-]{,1}[0-9]+\.{,1}[0-9]*) (kHz|MHz)",row['shift'])
        mult = (1e3 if shift.groups()[1]=='kHz' else 1e6) if shift else 0
        freq_tx = freq_rx + (float(shift.groups()[0]) * mult if shift else 0)
        name = row['(N)ome']
        tone = re.match("([0-9]+\.{,1}[0-9]*)",row['tono'])
        tone_tx = float(tone.group()) if tone else None
        tone_rx = None
        isNarrowBw = False
        isLowPower = False
        yield (name,freq_rx,freq_tx,tone_rx,tone_tx,isNarrowBw,isLowPower)

offsets = {
    'channel_name': 0x7000,
    'channel_data': 0x3000,
    'vfoa_data': 0x3010,
    'vfob_data': 0x3020
}

lengths = {
    'channel_data' : 16,
    'channel_name': 11
}

def transfer_channels(s_file,t_file,d_file,read_function,extract_function,start_channel=1,channels=1000):
    source = read_function(source_file)
    print(f'{len(source)} rows read from source file')
    buffer = read_data_file(template_file)
    channel = start_channel
    for (name,freq_rx,freq_tx,tone_rx,tone_tx,isNarrowBw,isLowPower) in extract_function(source):
        print(f'{channel} {name} {freq_rx} {freq_tx} {tone_rx} {tone_tx} {isNarrowBw} {isLowPower}')
        write_channel(buffer,channel,name,freq_rx,freq_tx,tone_rx,tone_tx,isNarrowBw,False)
        channel=channel+1
        if channel >= start_channel + channels:
            break
    write_data_file(buffer,dest_file)


#source_file = "d:/lpdpmr.csv"
#source_file = 'd:/Baofeng_UV-5R_20231108.csv'
source_file = 'd:/pontixls.csv'
template_file = "d:/uv13.data"
dest_file = "d:/pippo-new.data"
#transfer_channels(source_file,template_file,dest_file,chirp_csv_read,chirp_csv_extract,1,3)
transfer_channels(source_file,template_file,dest_file,ik2ane_csv_read,ik2ane_csv_extract,100,500)
