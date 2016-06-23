# from cffi import FFI
# import ctypes.util
# import numpy

# ffi = FFI()

# ffi.cdef("""
#  // int printf(const char *format, ...);   // copy-pasted from the man page
#  int strcmp(const char *format, const char *s);   // copy-pasted from the man page
# """)
# C = ffi.dlopen(None)                     # loads the entire C namespace

# # arg = ffi.new("char[]", "world")         # equivalent to C code: char arg[] = "world";

# # C.printf("hi there, %s.\n", arg) 
# C.strcmp('ok', 'ok')


# ffi.cdef("""
#   int ff_acelp_decode_8bit_to_1st_delay3(int ac_index);
#   """)
# C = ffi.dlopen(ctypes.util.find_library("libavcodec"))                     # loads the entire C namespace
# C.ff_acelp_decode_8bit_to_1st_delay3(200)

# from subprocess import call
import pika
import re
from subprocess import run
from subprocess import call
import subprocess
import wave
import math
import logging

logger = logging.getLogger('fluency.file_splitter')


work_dir = '/tmp/decode'
rabbit_ip = '172.17.0.2'
storage = 'http://192.168.1.4/back/stories'

# call(["ls", "-l"])
# call(["ffmpeg", '-h'])
# call(['pwd', '.'])
# call(['cd', '/home/prj/'])

# run(['rm', '/home/prj/1w*.wav'])

# out = run(["ls", "-l"], stdout=subprocess.PIPE)


# inp_f = '/home/feech/prj/49.avi'
# out_f = '/tmp/out.mp3'
# out = run(['ffmpeg', '-i', inp_f , '-vn', '-f', 'mp3', out_f])

# t = '00:20:16,190 --> 00:20:17,490'

def sec(str):
    sec = 0
    sec+= 3600 * float(str[0:2])
    sec+= 60 * float(str[3:5])
    sec+= float(str[6:8])
    if len(str)>9:
        sec+= float(str[9:])/1000

    return sec

def split_subtitles(file_name):
    '''
      '/home/feech/prj/1.txt'
    '''
    state = 0
    snippets = []
    f = None
    sentence = ''
    time_span_c = None
    for i in open(file_name):
        time_span = re.findall(r'\d\d:\d\d:\d\d\,\d*', i)
        if len(time_span)>0:
            state =1

        if state == 2:
            if len(i.strip())==0:
                state = 0
            else:
                sentence += i

        if state == 1:
            time_span_c = [sec(time_span[0]), sec(time_span[1])] 
            state =2

        if state==0 and time_span_c is not None and len(sentence)>0:
            snippets.append([time_span_c, sentence.replace('\n', ' ')])
            time_span_c = None
            sentence=''

    # to prevent cut voice because incorrect len of snippets in subtitles
    # for i, snippet in enumerate(snippets[:-1]):
    #     snippet[i][0][1] = snippet[i+1][0][0]

    return snippets





# data=pandas.read_csv('train.csv', index_col='PassengerId')

def processing(in_wav, snippets, dist, story_id):

    wr = wave.open(in_wav, 'rb')

    for i, snippet in enumerate(snippets):
        print(i, snippet)
        segment = snippet[0]
        wr_name = work_dir+'/1w%d.wav'%i

        ww = wave.open(wr_name, 'wb')
        ww.setparams((wr.getnchannels(),
            wr.getsampwidth(),
            wr.getframerate(),
            0, 
            'NONE',
            'not compressed'))
        wr.setpos(math.floor(segment[0]*wr.getframerate()))
        data = wr.readframes(math.floor((segment[1]-segment[0])*wr.getframerate()))
        ww.writeframes(data)
        ww.close()

        wo_name = work_dir + '/1w%d.mp3'%i
        pr = run(['ffmpeg', '-i', wr_name , '-vn', '-y', '-f', 'mp3', wo_name], stdout=None)
        if pr.returncode != 0:
            raise Exception()

        print('++++')
        pr = run(['http', '--ignore-stdin', '-f', 'POST', dist, 
            'story_id=%s'%story_id,
            'num=%d'%i,
            'from=%f'%segment[0],
            'to=%f'%segment[1],
            'text=%s'%snippet[1],
            'file@%s'%wo_name]
            )
        print('++++')
        if pr.returncode !=0:
            raise Exception()
    wr.close()


def callback(ch, method, properties, _body):
    print(" [x] Received %r" % _body)
    print(" [x] Received m %r" % method)
    print(" [x] Received p %r" % properties)

    story_id = _body.decode()
    # download subtitles
    # download media
    # convert to mp3
    # convert to wav
    # split subtitles
    # split wav -> convert each of peaces -> remove
    # remove all
    pr = None 
    try:

        pr = run(['wget', '-O', work_dir+'/subtitles', storage+'/subtitles?story_id=%s'%story_id])
        # @todo to check if necessarily to close stdout 
        if pr.returncode != 0:
            raise Exception()

        pr = run(['wget', '-O', work_dir+'/file.media', storage+'/%s/file'%story_id])
        if pr.returncode != 0:
            raise Exception()

        pr = run(['ffmpeg', '-i', work_dir+'/file.media' , '-vn', '-y', '-f', 'mp3', work_dir+'/file.mp3'])
        if pr.returncode != 0:
            raise Exception()

        pr = run(['http', '--ignore-stdin', '--timeout', '1200', '-f', 'POST', storage+'/file', 'story_id=%s'%story_id, 'file@%s'%(work_dir+'/file.mp3')])
        if pr.returncode != 0:
            raise Exception()

        pr = run(['ffmpeg', '-i', work_dir+'/file.media' , '-vn', '-y', '-f', 'wav', work_dir+'/file.wav'])
        if pr.returncode != 0:
            raise Exception()

        pr = None
        snippets = split_subtitles(work_dir+'/subtitles')
        processing(work_dir+'/file.wav', snippets, storage+'/snippet', story_id)


        ch.basic_ack(delivery_tag = method.delivery_tag)

    except Exception as e:
        print('error message: ' + e)
        if not pr is None:
            print('run failed: ', pr)
    else:
        print('undetected error...')
    finally:
        run(['rm', work_dir+'/*'])
    
    print('exit ... ')
    exit(0)


if __name__ == '__main__':
    # print('ok')

    pr = run(['mkdir', work_dir])
    print(pr)
    pr = run(['rm', '-f', work_dir+'/*'])
    print(pr)
    
    connection = pika.BlockingConnection(pika.ConnectionParameters(
            host=rabbit_ip))
    channel = connection.channel()

    channel.queue_declare(queue='queue_on_split')

    channel.basic_consume(callback, queue='queue_on_split', no_ack=False)

    print(' [*] Waiting for messages. To exit press CTRL+C')
    channel.start_consuming()

