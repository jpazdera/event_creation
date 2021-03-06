
from ptsa.data.readers.BaseEventReader import BaseEventReader
from parsers.fr_log_parser import fr_log_parser_wrapper
from parsers.pal_log_parser import pal_log_parser_wrapper
from parsers.math_parser import math_parser_wrapper
from parsers.catfr_log_parser import catfr_log_parser_wrapper
from parsers.ltpfr_log_parser import ltpfr_log_parser_wrapper
from parsers.base_log_parser import EventComparator
from alignment.system2 import System2Aligner
from alignment.system1 import System1Aligner
import numpy as np
import os
import re
from viewers.view_recarray import pprint_rec, to_json, from_json
from parsers.base_log_parser import StimComparator

DATA_ROOT = '/Volumes/rhino_mount/data/eeg/'

FR1_SYS1_SESSIONS = (('R1001P', 1, 'R1001P_13Oct14_1457.062.063.FR1_1.sync.txt'),
                     ('R1006P', 0, 'R1006P_11Feb15_1503.072.129.FR1_0.sync.txt'),
                     ('R1026D', 0, 'R1026D_22Feb15_0908.074.075.FR1_0.sync.txt'),
                     ('R1083J', 0, 'R1083J_13Sep15_1129.087.088.FR1_0.sync.txt'),
                     ('R1083J', 1, 'R1083J_14Sep15_1429.087.088.sync.txt'),
                     ('R1083J', 1, 'R1083J_14Sep15_1429.087.088.FR1_1.sync.txt'),
                     ('R1083J', 2, 'R1083J_15Sep15_1130.087.088.FR1_2.sync.txt'))

FR1_SYS2_SESSIONS = (('R1170J_1', 0),
                     ('R1170J_1', 1),
                     ('R1170J_1', 2))

FR2_SESSIONS = (('R1001P', 1, 'R1001P_17Oct14_1434.062.063.FR2_1.sync.txt'),
                ('R1002P', 0, 'R1002P_19Nov14_1458.078.079.FR2_0.sync.txt'))

FR3_SESSIONS = (('R1163T', 0),
                ('R1124J_1',0),
                ('R1124J_1',1),
                ('R1145J_1',0),
                ('R1154D', 0),
                ('R1154D', 1),
                ('R1154D', 2),
                ('R1154D', 3),
                ('R1161E', 0),
                ('R1161E', 1),
                ('R1163T', 1),
                ('R1166D', 0),
                ('R1166D', 1),
                ('R1170J_1', 0),
                ('R1170J_1', 1))

FR4_SESSIONS = (('R1076D', 0),
                ('R1196P', 0))

PAL1_SYS1_SESSIONS = (('R1028M', 1, 'R1028M_28Feb15_1020.066.067.PAL1_1.sync.txt'),
                      ('R1003P', 1, 'R1003P_18Nov14_1420.105.106.PAL1_1.sync.txt'),)

PAL1_SYS2_SESSIONS = (('R1196N', 2),
                      ('R1196N', 3),
                      ('R1196N', 4))

PAL2_SESSIONS = (('R1003P', 0, 'R1003P_20Nov14_1029.105.106.PAL2_0.sync.txt'),
                 ('R1003P', 1, 'R1003P_23Nov14_1317.105.106.PAL2_1.sync.txt'))

PAL3_SESSIONS = (('R1175N', 0),
                 ('R1196N', 0))

CATFR1_SYS1_SESSIONS = (('R1016M', 0, 'R1016M_20Jan15_1032.129.130.sync.txt'),
                        ('R1028M', 0, 'R1028M_27Feb15_1109.066.067.catFR1_0.sync.txt'),)

CATFR1_SYS2_SESSIONS = (('R1127P_2', 0),
                        ('R1171M', 0))

CATFR2_SESSIONS = (('R1016M', 0, 'R1016M_21Jan15_1834.128.129.catFR2_0.sync.txt'),
                   ('R1041M', 0, 'R1041M_14Apr15_1941.112.113.catFR2_0.sync.txt'))

LTPFR_SESSIONS = (('LTP107', 0),
                  ('LTP108', 0))

EEG_FILE_REGEX = r'R1[0-9]{3}[A-Z]_\d{2}[A-z]{3}\d{2}_\d{4}'


parsers = {
    'FR': fr_log_parser_wrapper,
    'PAL': pal_log_parser_wrapper,
    'catFR': catfr_log_parser_wrapper,
    'math': math_parser_wrapper
}

def compare_stimulation_parameters(event1, event2):
    pass

def event_comparison_exceptions(event1, event2, field, parent_field=None):
    if field == 'eegfile':
        # SESS_END might come just after the recording has stopped, so it shouldn't have an eeg file
        if event1['type'] == 'SESS_END': #
            return True

        if event1['eegfile'] == '' and event2['eegfile'] == './.':
            return True

        # Comparing only eegfile basename because it may be stored in a different location
        try:
            basename1 = ''.join(event1['eegfile'].split('_')[-2:])
        except AttributeError:
            basename1 = ''.join(event1['eegfile'][0].split('_')[-2:])

        try:
            basename2 = ''.join(event2['eegfile'].split('_')[-2:])
        except AttributeError:
            basename2 = ''.join(event2['eegfile'][0].split('_')[-2:])

        # Ugly, but for first subject, name was originally different
        if basename1 == basename2.replace('REO001P', 'R1001P'):
            return True

    if field == 'subject':
        try:
            ev2_subj = event2['subject'].split('_')[0]
        except AttributeError:
            ev2_subj = event2['subject'][0].split('_')[0]

        return event1['subject'] == ev2_subj

    if field == 'stim_list' and event1['stim_list'] == 1 and event2['stim_list'] == -999:
        return True

    # there is an allowable difference of up to 5 ms for eeg offset between new and old events
    if field == 'eegoffset' and abs(event1['eegoffset'] - event2['eegoffset']) <= 25:
        return True

    # There is an allowable difference of up to 1.5 ms for mstime between new and old events
    if field == 'mstime' and np.abs(event1['mstime'] - event2['mstime']) <= 4:
        return True

    # There is an allowable difference of up to 1ms for recall time between old and new events
    if field == 'rectime' and np.abs(event1['rectime'] - event2['rectime']) <= 1:
        return True

    # stimParams do not matter if it is not a STIM or STIM_OFF event
    # stimParams are propagated through events during stimulation in the new events
    if parent_field == 'stimParams' and event1['type'] != 'STIM' and event1['type'] != 'STIM_OFF':
        return True

    # Recalled is limited to True and False in new events, and is set to False where old events were -999
    if field == 'recalled' and event1['recalled'] == False and event2['recalled'] == -999:
        return True

    # stimList is limited to True and False in new events, and is set to False where old events were -999
    if field == 'stim_list' and event1['stim_list'] == False and event2['stim_list'] == -999:
        return True

    # For practice list events, old events had list improperly as -999 instead of -1
    if field == 'list' and event1['list'] == -1 and event2['list'] == -999:
        return True

    # Word Number is still not filled in for practice events, but is now -1 (like intrusions) rather than -999
    if field == 'wordno' and event1['list'] == -1 and event2['wordno'] == -999:
        return True

    # Serial position was not properly recorded for practice list in old events
    if field == 'serialpos' and event1['list'] == -1 and event2['serialpos'] == -999:
        return True

    # Word during word_off was not recorded for practice lists in old events
    if field == 'word' and event1['type'] == 'PRACTICE_WORD_OFF' and event1['list'] == -1:
        return True

    # Word, word number, serial position, rectime, and recalled were not marked for old word_off events
    if (field in ['word', 'wordno', 'serialpos', 'rectime', 'recalled']) and event1['type'] == 'WORD_OFF':
        return True

    # msoffset was recorded as -999 in old events for REC_START
    if field == 'msoffset' and event1['type'] == 'REC_START' and event2['msoffset'] == -999:
        return True

    # In old vocalization events, wordno, intrusion, msoffset, and mstime were -999
    # In new vocalization events, wordno and intrusion are -1, and msoffset and mstime are accurate
    if field in ('wordno', 'intrusion', 'msoffset', 'mstime') and event1['type'] == 'REC_WORD_VV':
        return True

    # In old Recall events, expVersion, serial position, recalled, and msoffset were -999 for REC_word events
    # SP is now set to true serial position, and recalled is set to true
    if field in ('expVersion', 'serialpos', 'recalled', 'msoffset') and event1['type'] == 'REC_WORD':
        return True

    # In old recall events, wordNo was not set for recalls that were XLIs but still in the wordpool
    if field == 'wordno' and event1['type'] == 'REC_WORD' and event1['intrusion'] == -1 and event2['intrusion'] == -1:
        return True

    # STIM events had an msoffset of 0, now have an msoffset of -1 to signify that offset is unknown
    if field == 'msoffset' and event1['type'] == 'STIM':
        return True

    # stimList was not set properly on stim lists for old REC events
    if field == 'stim_list' and event1['type'] in ('REC_START', 'REC_WORD', 'REC_WORD_VV') \
            and event1['stim_list'] == True and event2['stim_list'] == -999:
        return True

    # During old stim events, word, word number, and serial position did not propagate through stim events
    if field in ('wordno', 'word', 'serialpos') and event1['type'] == 'STIM':
        return True

    # Stimulation events that occurred before the start of the session were not recorded in old events
    if field is None and event2 is None and event1['type'] == 'STIM' and event1['eegoffset'] == -1:
        return True

    if field == 'subject' and event1['subject'] == 'R1001P' and event2['subject'] == 'REO001P':
        return True

    if field == 'eegoffset' and event1['eegoffset'] < 0 and event2['eegoffset'] < 0:
        return True

    return False

def fr1_comparison_exceptions(event1, event2, field, parent_field=None):
    if event_comparison_exceptions(event1, event2, field, parent_field):
        return True

    # is_stim was set to -999 for all old FR1 events, now set to False
    if field == 'is_stim' and event1['is_stim'] == False and event2['is_stim'] == -999:
        return True

    # For some reason practice words weren't recorded in early FR1 events
    if field == 'word' and event1['type'] == 'PRACTICE_WORD' and event2['word'] == 'X':
        return True

    if field in ('wordno', 'intrusion') and event1['subject'] == 'R1039M' and event1['word'] == 'RELOJ':
        return True


    if field in ('rectime', 'recalled', 'wordno', 'word', 'intrusion') and event1['subject'] == 'R1052E' \
            and event1['session'] == 0:
        return True

    if field is None and event2 and event2['subject'] == 'R1042M' and event2['type'] == 'REC_WORD' and \
                    event2['word'] in ("'I'M", "'I", "'NOT"):
        return True

    if not field is None and event1['word'] in ('TOE', 'SINK', 'ROSE'):
        return True

    if field == 'subject' and event1['subject'] == 'R1055J' and event2['subject'] == 'TJ086':
        return True

    if field == 'rectime' and event1['type'] in ('WORD', 'REC_WORD') and event1['subject'] == 'R1096E' and \
                    event1['list'] <= 3:
        return True

    if field is None and event1 and event1['type'] in ('REC_WORD', 'REC_WORD_VV') and event1['list'] <= 3 and\
            event1['subject'] == 'R1096E':
        return True

    if field is None and event2 and event2['type'] in ('REC_WORD', 'REC_WORD_VV') and event2['list'] <= 3 and \
                    event2['subject'] == 'R1096E':
        return True

    if field == 'eegfile' and event1['subject'] == 'R1106M' and event1['eegfile'] == 'R1106M_FR1_1_14Nov15_1805':
        return True

    if field in ('wordno', 'intrusion') and event1['word'] == 'RELOJ' and event1['subject'] == 'R1134T':
        return True

    # R1156N Session 3 had a specific problem where it assigned an eegfile past the end of the recording
    if field in ('eegfile', 'eegoffset') and event1['subject'] == 'R1156D' and \
            event1['eegfile'] == '' and os.path.basename(event2['eegfile'][0]) == 'R1156D_FR1_3_21May16_1625':
        return True

    # R1162N's eegfile field is all messed up.
    if field in ('eegfile', 'eegoffset') and event1['subject'] == 'R1162N' and \
            event1['eegfile'] == 'R1162N_FR1_0_18Apr16_1033':
        return True

    # For some reason, R1171M's practice list was marked as list 1
    if field == 'list' and event1['list'] == -1 and event2['list'] == 1 and event1['mstime'] <= 1462394190103 and\
            event1['subject'] == 'R1171M':
        return True

    # Bizarre annotations in R1176M
    if field is None and event2 and event2['type'] == 'REC_WORD' and event2['word'] == "'I" and \
            event2['subject'] == 'R1176M':
        return True

    # More bizarre annotations in R1177M
    if field is None and event2 and event2['type'] == 'REC_WORD' and event2['subject'] == 'R1177M':
        return True

    if field == 'word' and event1['subject'] in ('R1060M', 'R1111M', 'R1130M', 'R1198M') and ' ' in event1['word']:
        return True

    if field is None and event2 and "'" in event2['word']:
        return True

    return False

def fr2_comparison_exceptions(event1, event2, field, parent_field=None):
    if event_comparison_exceptions(event1, event2, field, parent_field):
        return True

    # isStim was set to -999 for all old FR1 events, now set to False
    if field == 'is_stim' and event1['is_stim'] == False and event2['is_stim'] == -999:
        return True

    # For some reason in FR2 events, stim_on events were marked as non-stim
    if field == 'is_stim' and event1['type'] == 'STIM_ON' and event1['is_stim'] == True and event2['is_stim'] == -999:
        return True

    # For some reason practice words weren't recorded in early FR1 events
    if field == 'word' and event1['type'] == 'PRACTICE_WORD' and event2['word'] == 'X':
        return True

    # DISTRACT_START Was never marked as is_stim even through it sometimes overlapped with stim
    if field == 'is_stim' and event1['type'] == 'DISTRACT_START' and event1['is_stim'] == True:
        return True


    if field is None and event2 and event2['subject'] == 'R1001P' and event2['type'] == 'REC_WORD_VV' and\
        event2['eegoffset'] == 859465:
        return True

    # Typo in  R1020J's FR2 file
    if field is None and event1 and event1['subject'] == 'R1020J' and event1['type'] == 'TRIAL' and \
                    event1['mstime'] == 1422461267297:
        return True
    if field is None and event2 and event2['subject'] == 'R1020J' and event2['type'] == 'TRIAL' and \
                    event2['mstime'] == 422461267297:
        return True

    # Weirdness in R1031M's annotations
    if field is None and event2 and event2['subject'] == 'R1031M' and event2['type'] == 'REC_WORD' and \
                    event2['word'] in ("'CCCC....'", "'DID"):
        return True

    # Weirdness in R1042M's annotations
    if field is None and event2 and event2['subject'] == 'R1042M' and event2['type'] == 'REC_WORD' and \
                    event2['word'] == "'STH":
        return True

    # Weirdness in R1069M's annotations
    if field is None and event2 and event2['subject'] == 'R1069M' and event2['type'] == 'REC_WORD' and \
                    event2['word'] == "'OH,":
        return True

    # More weirdness in R1177M's annotations
    if field is None and event2 and event2['subject'] == 'R1177M' and event2['type'] == 'REC_WORD':
        return True

    # And again in R1184M
    if field is None and event2 and event2['subject'] == 'R1184M' and event2['type'] == 'REC_WORD':
        return True

    if field == 'word' and event1['subject'] in ('R1028M') and ' ' in event1['word']:
        return True

    return False


def pal_comparison_exceptions(event1, event2, field, parent_field=None):
    if event_comparison_exceptions(event1, event2, field, parent_field):
        return True

    if field == 'vocalization' and event1['vocalization'] == 0 and event2['vocalization'] == -999:
        return True

    if field == 'resp_pass' and event1['resp_pass'] == 0 and event2['resp_pass'] == -999:
        return True

    if field in ('probe_word', 'resp_word', 'study_1', 'study_2') and \
        event1[field] == '' and event2[field] == -999:
        return True

    if field == 'stimType' and event1['stimType'] == '' and event2['stimType'] in ('[]', 'NONE'):
        return True

    if field == 'expecting_word' and event1['expecting_word'] == '' and event2['expecting_word'] == -999:
        return True

    if field == 'RT' and abs(event1['RT'] - event2['RT']) <= 2:
        return True

    if field == 'intrusion' and event1['intrusion'] == -1 and event2['intrusion'] > 0:
        return True

    if field == 'stimTrial' and event1['stimTrial'] == False and np.isnan(event2['stimTrial']):
        return True

    if field == 'probepos' and event1['type'] == 'PRACTICE_ORIENT_OFF' and event2['probepos'] == -999:
        return True

    if field in ('probe_word', 'resp_pass', 'correct', 'cue_direction',
                 'expecting_word', 'resp_word', 'RT', 'intrusion') and \
                    event1['type'] in ('PRACTICE_ORIENT', 'PRACTICE_ORIENT_OFF', 'PRACTICE_PAIR', 'PRACTICE_PROBE') and \
                    event2[field] ==  -999:
        return True

    if field in ('resp_pass', 'correct', 'study_1', 'study_2', 'resp_word', 'RT', 'intrusion') and\
                    event1['type'] in ('PRACTICE_RETRIEVAL_ORIENT', 'PRACTICE_RETRIEVAL_ORIENT_OFF', 'REC_START') and\
                    event2[field] == -999:
        return True

    if field == 'list' and event1['list'] == -1 and event2['list'] == 0 and event1['type'] == 'REC_EVENT':
        return True

    if field in ('probe_word', 'expecting_word', 'serialpos', 'probepos', 'list') and \
                    event2['type'] == 'PRACTICE_RETRIEVAL_ORIENT_OFF':
        return True

    if field == 'list' and event2['list'] == -999 and event2['type'] == 'TRIAL':
        return True

    if field in ('probe_word', 'cue_direction', 'expecting_word') and event2[field] == -999 and \
                    event1['type'] in ('STUDY_ORIENT',):
        return True

    if field in ('resp_word', 'probe_word', 'probepos', 'cue_direction',
                 'resp_pass', 'RT', 'correct', 'expecting_word')  and event2[field] == -999 and \
                    event1['type'] in ('STUDY_ORIENT_OFF', ):
        return True

    if field in ('probe_word', 'cue_direction', 'expecting_word') and event2[field] == -999 and \
                    event1['type'] == 'STUDY_PAIR':
        return True

    if event1 and event1['type'] in ('PAIR_OFF', 'RETRIEVAL_ORIENT_OFF', 'PROBE_OFF', 'TEST_ORIENT') and \
                    event2 and event2[field] == -999:
        return True

    if event1 and event1['type'] == 'RETRIEVAL_ORIENT_OFF':
        return True

    if event1 and event1['type'] in ('TEST_PROBE', 'PRACTICE_PROBE') and field in ('study_1', 'study_2'):
        return True

    if event1 and event1['type'] == 'REC_START' and field in ('serialpos', 'list') and event2[field] == -999:
        return True

    if field == 'list' and event2['type'] == 'REC_EVENT' and event2['list'] == 0:
        return True

    if field == 'intrusion' and event1['type'] in ('STUDY_ORIENT', 'STUDY_PAIR', 'STUDY_ORIENT_OFF',
                                                   'TEST_PROBE', 'PRACTICE_PROBE') and \
                    event2['intrusion'] == -999:
        return True

    if field == 'list' and event1['type'] == 'SESS_END' and event2['list'] == -999:
        return True

    if field == 'probe_word' and event1['type'] == 'PRACTICE_RETRIEVAL_ORIENT' and event2['probe_word'] == 0:
        return True

    if field == 'is_stim' and event1['is_stim'] == 0 and event2['is_stim'] == -999:
        return True

    if field == 'list' and event2['list'] == -999:
        return True

    if field is None and event1 and event1['type'] == 'ENCODING_START':
        return True

    if field is None and event2 and event2['type'] == 'STUDY_START':
        return True

    if field == 'correct' and event1['correct'] == 0 and event2['correct'] == -999:
        return True

    if field == 'intrusion' and event1['intrusion'] >= 0 and event2['intrusion'] > 0 and event1['correct'] == 0:
        return True

    if field in ('study_1', 'study_2', 'probe_word', 'expecting_word', 'probepos', 'cue_direction', 'resp_pass',
                 'RT', 'intrusion', 'resp_word', 'serialpos', 'correct', ) and \
        event1['type'] == 'STIM_ON':
        return True

    if field is None and event1 and event1['type'] == 'ENCODING_START':
        return True

    # Weirdness in annotations on R1036M
    if event2 and event2['subject'] == 'R1036M' and event2['resp_word'] == "'OH":
        return True

    # Weird errors with annotation in R1082N
    if event1 and (event1['resp_word'] in ('GRAA', 'BASTON', 'NINO', 'CORAZON', 'BANO', 'BOLAGRAFO', 'PEZUNA', 'ARBOL') \
                   or event1['study_1'] == 'POLO') and event1['subject'] == 'R1082N':
        return True

    if event2 and event2['type'] == 'REC_EVENT' and event2['mstime'] == 1443462572814:
        return True

    # Appears session was re-annotated
    if field in ('RT', 'resp_word', 'resp_pass', 'vocalization', 'serialpos') and event1['subject'] == 'R1097N':
        return True
    if field is None and event1 and event1['subject'] == 'R1097N' and event1['type'] == 'REC_EVENT':
        return True
    if field is None and event2 and event2['subject'] == 'R1097N' and event2['type'] == 'REC_EVENT':
        return True

    # Difference due to word repetition
    if field is 'RT' and event1['subject'] == 'R1109N' and event1['mstime'] == 1447973326664:
        return True
    if field is None and event1 and event1['type'] == 'REC_EVENT' and event1['resp_word'] == 'STREET':
        return True

    # Somehow some rec_events are minutes into the future
    if field is None and event2 and event2['type'] == 'REC_EVENT' and event2['RT'] > 30000:
        return True

    if field == 'cue_direction' and event1['subject'] == 'R1175N' and event1['cue_direction'] == 1 \
                and event1['mstime'] == 1464112784636:
        return True

    if field == 'subject' and event1['subject'] == 'R1185N' and event2['subject'] == 'NIH042':
        return True

    if field == 'cue_direction' and event1['subject'] in ('R1196N', 'R1202M') and event1['cue_direction'] == 1:
        return True

    if event2 and event2['resp_word'] in ("'AAAA...'", '\'THAT"S...\''):
        return True

    # Weird annotation in R1036M
    if field in ('RT', 'resp_word', 'correct') and event1['resp_word'] in ('BOARD', 'FOOT') and \
                    event1['subject'] == 'R1036M':
        return True
    if field is None and event2 and event2['type'] == 'REC_EVENT' and event2['resp_word'] in ("'FOOT'", "'B-O-A-R-D'"):
        return True

    if field in ('RT', 'resp_word') and event1['subject'] == 'R1060M' and event2['resp_word'] == "'KNEAD'":
        return True
    if field is None and event2 and event2['resp_word'] == "'KNEAD'":
        return True

    if field in ('resp_word', 'correct', 'intrusion') \
            and event1['resp_word'] in ('ZOOLOGICO', 'TIBURON', 'TELARANA', 'JARRON'):
        return True

    if field == 'stimType' and event1['stimType'] == '' and event2['stimType'] == -999:
        return True

    if field == 'stimTrial' and event1['stimTrial'] == 0 and event2['stimTrial'] == -999:
        return True

    if not field in ('eegfile', 'eegoffset', 'mstime') and event1 and  event1['type'] in ('STIM', 'STIM_OFF'):
        return True

    if field == 'stimTrial' and event1['list'] in (5, 6, 11, 12, 13, 14, 15, 16, 18, 21, 23) and \
            event1['stimTrial'] == 1:
        return True

    if field == 'stimTrial' and event2['stimTrial'] == -999:
        return True

    if field == 'cue_direction' and event1['mstime'] == 1464650407753 and event1['subject'] == 'R1175N':
        return True



    if field == 'resp_word' and event1['subject'] in ('R1016M', 'R1060M') and ' ' in event1['resp_word']:
        return True

    if field == 'RT' and event1['subject'] in ('R1060M', 'R1087N', 'R1090C', 'R1091N', 'R1106M', 'R1149N', 'R1031M',
                                               'R1082N', 'R1196N') :
        return True

    if field == 'is_stim' and event1['is_stim'] == 1 and event1['type'] == 'STIM_ON':
        return True

    if field == 'is_stim' and event1['is_stim'] and event1['type'] == 'REC_START' and event2['is_stim'] == -999:
        return True

    if field == 'stim_type' and event1['stim_type'] == '' and \
            ( event2['stim_type'] == 'NONE' or event2['stim_type'] == -999 or event2['stim_type'] == '[]'):
        return True

    if field == 'stim_list' and event1['stim_list'] == 0 and np.isnan(event2['stim_list']):
        return True

    # R1207J's session 0 had an improper cue direction
    if field == 'cue_direction' and event1['subject'] == 'R1207J' and event1['study_1'] == 'BEAM':
        return True

    return False


def catfr_comparison_exceptions(event1, event2, field, parent_field=None):
    if event_comparison_exceptions(event1, event2, field, parent_field):
        return True

    if field == 'is_stim' and event1['is_stim'] == False and event2['is_stim'] == -999:
        return True

    if  field in ('recalled', 'rectime', 'intrusion', 'category', 'category_num') and event1['subject'] == 'R1016M' \
            and event1['word'] in ('PLIERS',):
        return True

    if field == 'category_num' and event1['subject'] == 'R1066P' and event1['word'] in ('OCEAN', 'CLOUD'):
        return True

    if field == 'word' and event1['type'] == 'PRACTICE_WORD' and event2['word'] == 'X':
        return True

    if field == 'stim_list' and event1['type'] in ('COUNTDOWN_END', 'ORIENT', 'STIM_ON',
                                                  'DISTRACT_START', 'DISTRACT_END','REC_END') and\
                    event2['stim_list'] == -999:
        return True

    if field in ('wordno', 'intrusion') and event2[field] == -1 and event1['subject'] == 'R1004D':
        return True


    if field in ('rectime', 'recalled') and event1['subject'] == 'R1026D' and event1['word'] == 'BLOCKS':
        return True
    if field is None and (event1 and event1['word'] == 'BLOCKS') or (event2 and event2['word'] == 'LOCKS'):
        return True

    if field in ('rectime', 'recalled', 'category', 'wordno', 'intrusion', 'categoryNum') and\
                event1['subject'] == 'R1066P' and event1['word'] in ('CLOUD','OCEAN'):
        return True

    if field == 'rectime' and event1['subject'] == 'R1105E':
        return True

    if field is None and event1 and event1['subject'] == 'R1105E' and event1['type'] in ('REC_WORD', 'REC_WORD_VV'):
        return True
    if field is None and event2 and event2['subject'] == 'R1105E' and event2['type'] in ('REC_WORD', 'REC_WORD_VV'):
        return True

    if field is None and event2 and event2['word'] == "'THERE" and event2['subject'] == 'R1176M':
        return True

    if field == 'word' and ' ' in event1['word'] and event1['subject'] == 'R1181E':
        return True

    if field == 'rectime' and event1['subject'] == 'R1189M':
        return True
    if field is None and event1 and event1['subject'] == 'R1189M' and event1['type'] in ('REC_WORD', 'REC_WORD_VV'):
        return True
    if field is None and event2 and event2['subject'] == 'R1189M' and event2['type'] in ('REC_WORD', 'REC_WORD_VV'):
        return True

    if field in ('rectime', 'recalled', 'category', 'categoryNum', 'intrusion') and event1['word'] in ('APPLE','STOVE'):
        return True

    if field is None and event2 and event2['word'] in ("'I", "'NOTHING,"):
        return True

    if field == 'word' and event1['subject'] == 'R1039M' and event1['type'] == 'REC_WORD' and '"' in event2['word'][0]:
        return True

    if field == 'word' and event1['type'] == 'REC_WORD' and ' ' in event1['word']:
        return True

    if field == 'RT' and event1['subject'] in ('R1060M', 'R1087M', 'R1090C', 'R1091N', 'R1106M', 'R1149N',
                                               'R1031M', 'R1082N', 'R1196M'):
        return True

    if field == 'resp_word' and event1['subject'] == 'R1112M' and event2['resp_word'] == 0:
        return True

    if field == 'is_stim' and event1['is_stim'] == 1 and event1['type'] == 'STIM_ON':
        return True

    return False


def fr3_comparison_exceptions(event1, event2, field, parent_field=None):
    if event_comparison_exceptions(event1, event2, field, parent_field):
        return True

    # Stims that occur before the beginning of the session are fine.
    if field is None and event2 and event2['type'] == 'STIM' and event2['eegoffset'] < 0:
        return True


    return False

def verbal_stim_comparison_exceptions(event1, event2, field_name1, field_name2):
    field1 = StimComparator.get_subfield(event1, field_name1)
    field2 = StimComparator.get_subfield(event2, field_name2)[0]
    try:
        field2_is_nan = np.isnan(field2)
    except:
        field2_is_nan = False

    if field1 == 0 and event1['is_stim'] == 0:
        return True

    if event1['type'] != 'STIM' and (field2_is_nan or field2 == '[]'):
        return True

    if not event1['is_stim'] and ((not event2['isStim']) or event2['isStim'] == -999) and not field1:
        return True

    if field_name1 in ('stim_params.anode_label', 'stim_params.cathode_label') and field1.upper() == field2.upper():
        return True

    if field_name1 == 'stim_params.anode_label' and field1 in ('LHC1', 'LHC5') and field2 in ('HC1', 'HC5') and \
                    event1['subject'] == 'R1192C':
        return True
    if field_name1 == 'stim_params.cathode_label' and field1 in ('LHC2', 'LHC6') and field2 in ('HC2', 'HC6') and \
                    event1['subject'] == 'R1192C':
        return True

    return False


def catfr2_stim_comparison_exceptions(event1, event2, field_name1, field_name2):
    if verbal_stim_comparison_exceptions(event1, event2, field_name1, field_name2):
        return True

    field1 = StimComparator.get_subfield(event1, field_name1)
    field2 = StimComparator.get_subfield(event2, field_name2)[0]

    if field_name1 in ('stim_params.anode_label', 'stim_params.cathode_label' ) and \
                    field1 in ('LHC5', 'LHC6') and field2 in ('HCH5', 'HCH6'):
        return True

    return False

def pal2_stim_comparison_exceptions(event1, event2, field_name1, field_name2):
    if verbal_stim_comparison_exceptions(event1, event2, field_name1, field_name2):
        return True

    field1 = StimComparator.get_subfield(event1, field_name1)
    field2 = StimComparator.get_subfield(event2, field_name2)[0]

    if not event1['is_stim'] and ((not event2['isStim']) or event2['isStim'] == -999) and not field1:
        return True

    return False

def ps_event_exceptions(event1, event2, field, parent_field=None):
    if field == 'exp_version':
        return True

    if field == 'eegfile':
        eeg_file_1 = '_'.join(os.path.basename(event1['eegfile']).split('_')[-2:])
        eeg_file_2 = '_'.join(os.path.basename(event2[0]['eegfile']).split('_')[-2:])
        if eeg_file_1 == eeg_file_2:
            return True

    if field == 'eegoffset' and abs(event1['eegoffset'] - event2[0]['eegoffset']) <= 25:
        return True

    # Individual "Burst" events are no longer created
    if field is None and event2 and event2['type'] == 'BURST':
        return True

    if field == 'type':
        return True

    if field == 'ad_observed' and event1['subject'] in \
            ('R1050M', 'R0156M', 'R1060M', 'R1069M', 'R1055J') and event1['ad_observed'] == 0:
        return True

    if field == 'eegfile' and event1['eegfile'] == '' and event2['eegfile'][0] == './.':
        return True

    if field == 'subject' and event1['subject'] == 'R1055J' and event2['subject'] == 'TJ086':
        return True

    if field == 'ad_observed' and event1['experiment'] == 'PS3' and event1['exp_version'] == '1.0':
        return True

    if field == 'eegoffset' and abs(event1['eegoffset'] - event1['eegoffset']) <= 40 and \
                    event1['subject'] in ('R1060M', 'R1096E'):
        return True

    if field == 'eegoffset' and abs(event1['eegoffset'] - event2['eegoffset']) <= 300 and \
                    event1['subject'] == 'R1105E':
        return True

    return False

def ps_sys2_event_exceptions(event1, event2, field, parent_field=None):
    if ps_event_exceptions(event1, event2, field, parent_field):
        return True

    if field == 'mstime' and abs(event1['mstime'] - event2['mstime']) < 10000:
        return True

    if field is None and event1 and event1['type'] == 'SESS_START':
        return True

    # R1166D had events past end of session
    if field is None and event2 and event2['subject'] == "R1166D" and event2['mstime'] >= 1461425757902:
        return True
    # R1195E had events past end of session
    if field is None and event2 and event2['subject'] == "R1195E" and event2['mstime'] >= 1468610881173:
        return True

    # Recording was stopped before last AD check in R1195E
    if field in ('eegfile', 'eegoffset') and event1['type'] == 'AD_CHECK' and event1['subject'] == 'R1195E':
        return True

    # R1184M's mstime is off by about 2 hours -- not a big deal, since it's only used to get timestamp
    if field == 'mstime' and abs(event1['mstime'] - event2['mstime']) < 8000000 and event1['subject'] == 'R1184M':
        return True
    return False

def ps_sys1_stim_comparison_exceptions(event1, event2, field_name1, field_name2):

    field1 = StimComparator.get_subfield(event1, field_name1)
    field2 = StimComparator.get_subfield(event2, field_name2)[0]

    if field_name1 in ('stim_params.n_bursts', 'stim_params.burst_freq') and field1 == 1 and field2 == -999:
        return True

    if event1['type'] == 'AD_CHECK':
        return True

    if field_name1 == 'stim_params.stim_duration' and field_name2 == 'pulse_duration' and \
            event1.stim_params.n_bursts > 1:
        return True

    if field1 == 0 or field1 == '' and 'BEGIN' in event1['type']:
        return True

    if field_name1 == 'stim_params.stim_duration' and field1 == 1 and event1['type'] == 'STIM_SINGLE_PULSE':
        return True

    if field_name1 == 'stim_params.pulse_freq' and field1 == -1 and event1['type'] == 'STIM_SINGLE_PULSE':
        return True

    if event1['type'] in ('PAUSED', 'UNPAUSED', 'SHAM') and field1 == '':
        return True

    if field_name1 in ('stim_params.anode_label', 'stim_params.cathode_label') and field1.upper() == field2.upper():
        return True

    return False


def check_event_creation(subject, experiment, session, is_sys2, comparator_inputs,
                         task_pulse_file=None, eeg_pulse_file=None,
                         eeg_file_stem=None, do_align=False):
    print('Testing: %s, %s: %d' % (subject, experiment, session))

    parser_type = parsers[re.sub(r'\d', '', experiment)]
    parser = parser_type(subject, session, experiment, base_dir=DATA_ROOT)

    print('Parsing events...')
    unaligned_events = parser.parse()

    print('Aligning events...')
    if do_align:
        if is_sys2:
            aligner = System2Aligner(subject, experiment, session, unaligned_events, False, DATA_ROOT)
            aligner.add_stim_events(parser.event_template, parser.persist_fields_during_stim)
            py_events = aligner.align(parser.START_EVENT)
        else:
            aligner = System1Aligner(unaligned_events, task_pulse_file, eeg_pulse_file, eeg_file_stem, DATA_ROOT)
            py_events = aligner.align()
    else:
        py_events = unaligned_events

    print('Loading mat events...')
    mat_events_reader = \
        BaseEventReader(
            filename=os.path.join(DATA_ROOT, subject, 'behavioral', experiment, 'session_%d' % session, 'events.mat'),
            common_root=DATA_ROOT
        )
    mat_events = mat_events_reader.read()

    print('Comparing...')
    comparator = EventComparator(py_events, mat_events, **comparator_inputs)
    found_bad, error_message = comparator.compare()

    if found_bad is True:
        assert False, error_message
    else:
        print('Comparison Success!')

    return py_events

FR1_STIM_COMPARISON = dict(
    fields_to_compare={
        'stim_params.anode_number': 'stimAnode',
        'stim_params.cathode_number': 'stimCathode',
        'stim_params.amplitude': 'stimAmp'
    },
    exceptions=verbal_stim_comparison_exceptions,
)
FR2_STIM_COMPARISON = FR1_STIM_COMPARISON

FR3_STIM_COMPARISON = dict(
    fields_to_compare={
        'stim_params.anode_number': 'stimParams.elec1',
        'stim_params.cathode_number': 'stimParams.elec2',
        'stim_params.amplitude': 'stimParams.amplitude',
        'stim_params.burst_freq': 'stimParams.burstFreq',
        'stim_params.n_bursts': 'stimParams.nBursts',
        'stim_params.pulse_freq': 'stimParams.pulseFreq',
        'stim_params.n_pulses': 'stimParams.nPulses',
        'stim_params.pulse_width': 'stimParams.pulseWidth'
    },
    exceptions=verbal_stim_comparison_exceptions,
)

CATFR_STIM_COMPARISON = dict(
    fields_to_compare={
        'stim_params.anode_number': 'stimAnode',
        'stim_params.cathode_number': 'stimCathode',
        'stim_params.anode_label': 'stimAnodeTag',
        'stim_params.cathode_label': 'stimCathodeTag',
        'stim_params.amplitude': 'stimAmp',
    },
    exceptions=catfr2_stim_comparison_exceptions
)

PAL_STIM_COMPARISON = dict(
    fields_to_compare={
        'stim_params.anode_number': 'stimAnode',
        'stim_params.cathode_number': 'stimCathode',
        'stim_params.anode_label': 'stimAnodeTag',
        'stim_params.cathode_label': 'stimCathodeTag',
        'stim_params.amplitude': 'stimAmp',
    },
    exceptions=verbal_stim_comparison_exceptions
)

PAL3_STIM_COMPARISON = dict(
    fields_to_compare = {
        'stim_params.anode_number': 'stimParams.elec1',
        'stim_params.cathode_number': 'stimParams.elec2',
        'stim_params.amplitude': 'stimParams.amplitude',
        'stim_params.burst_freq': 'stimParams.burstFreq',
        'stim_params.n_bursts': 'stimParams.nBursts',
        'stim_params.pulse_freq': 'stimParams.pulseFreq',
        'stim_params.n_pulses': 'stimParams.nPulses',
        'stim_params.pulse_width': 'stimParams.pulseWidth'
    },
    exceptions=verbal_stim_comparison_exceptions
)

PS_SYS1_STIM_COMPARISON = dict(
    fields_to_compare= {
     'stim_params.anode_number': 'stimAnode',
     'stim_params.cathode_number': 'stimCathode',
     'stim_params.anode_label': 'stimAnodeTag',
     'stim_params.cathode_label': 'stimCathodeTag',
     'stim_params.amplitude': 'amplitude',
     'stim_params.pulse_freq': 'pulse_frequency',
     'stim_params.burst_freq': 'burst_frequency',
     'stim_params.n_bursts': 'nBursts',
     'stim_params.stim_duration': 'pulse_duration',
    },
    exceptions=ps_sys1_stim_comparison_exceptions,
)
PS_SYS2_STIM_COMPARISON = dict(
    fields_to_compare= {
     'stim_params.anode_number': 'stimAnode',
     'stim_params.cathode_number': 'stimCathode',
     'stim_params.anode_label': 'stimAnodeTag',
     'stim_params.cathode_label': 'stimCathodeTag',
     'stim_params.amplitude': 'amplitude',
     'stim_params.pulse_freq': 'pulse_frequency',
     'stim_params.burst_freq': 'burst_frequency',
     'stim_params.n_bursts': 'nBursts',
     'stim_params.stim_duration': 'pulse_duration',
    },
    exceptions=ps_sys1_stim_comparison_exceptions,
    match_field='eegoffset'
)


all_ignore = ('exp_version', 'expVersion', 'montage', 'stim_params', 'stimParams', 'session', 'experiment', 'protocol')

FR1_SYS2_COMPARATOR_INPUTS = dict(
    field_switch={'word': 'item', 'wordno': 'itemno', 'stim_list': 'stimList', 'is_stim': 'isStim'},
    field_ignore=all_ignore,
    exceptions = fr1_comparison_exceptions,
    type_ignore=('INSTRUCT_START','INSTRUCT_END',
                 'PRACTICE_REC_START', 'PRACTICE_REC_END',
                 'SESSION_SKIPPED', 'INSTRUCT_VIDEO', 'STIM_OFF', 'B', 'E')
)
FR3_SYS2_COMPARATOR_INPUTS = dict(
    field_switch={'word': 'item', 'wordno': 'itemno', 'stim_list': 'stimList', 'is_stim': 'isStim'},
    field_ignore=all_ignore,
    exceptions = fr3_comparison_exceptions,
    type_ignore=('INSTRUCT_START','INSTRUCT_END',
                 'PRACTICE_REC_START', 'PRACTICE_REC_END',
                 'SESSION_SKIPPED', 'INSTRUCT_VIDEO', 'STIM_OFF', 'B','E')
)

PS_COMPARATOR_INPUTS = dict(
    field_switch={'ad_observed': 'ADs_present', 'exp_version': 'expVersion'},
    field_ignore = ('amplitude', 'burst_i', 'pulse_frequency', 'burst_frequency',
                     'nBursts', 'pulse_duration', 'stimAnode', 'stimAnodeTag','stimCathode',
                     'stimCathodeTag', 'stimAmp', 'is_stim',
                    'montage', 'stim_params', 'stimParams', 'session','protocol'),
    exceptions=ps_event_exceptions,
    type_ignore=('STIM_OFF', 'END_EXP', 'BEGIN_PS3', 'AMPLITUDE_CONFIRMED'),
    type_switch={'STIM': ('STIMULATING', 'BEGIN_BURST')}
)

PS_SYS2_COMPARATOR_INPUTS = dict(
    field_switch={'ad_observed': 'has_ADs', 'is_stim': 'stimOn',},
    field_ignore = ('amplitude', 'burst_i', 'pulse_frequency', 'burst_frequency',
                     'nBursts', 'pulse_duration', 'stimAnode', 'stimAnodeTag','stimCathode',
                     'stimCathodeTag', 'stimAmp', 'hostTime', 'stimDuration', 'exp_version', 'experiment',
                    'montage', 'stim_params', 'stimParams', 'session','protocol', 'msoffset', 'nPulses', 'pulseWidth'),
    exceptions=ps_sys2_event_exceptions,
    type_ignore=('STIM_OFF', 'END_EXP', 'BEGIN_PS3', 'AMPLITUDE_CONFIRMED'),
    type_switch={'STIM': ('STIMULATING', 'BEGIN_BURST')},
    match_field='eegoffset'
)


FR1_SYS1_COMPARATOR_INPUTS = dict(
    field_switch={'word': 'item', 'wordno': 'itemno',  'stim_list': 'stimList', 'is_stim': 'isStim'},
    field_ignore= all_ignore + (
                  'stimAnode', 'stimAnodeTag',
                  'stimCathode', 'stimCathodeTag',
                  'stimAmp', 'stimLoc',),
    exceptions=fr1_comparison_exceptions,
    type_ignore=('INSTRUCT_START', 'INSTRUCT_END',
                 'PRACTICE_REC_START', 'PRACTICE_REC_END',
                 'SESSION_SKIPPED', 'INSTRUCT_VIDEO', 'STIM_OFF',
                 'B', 'E', 'SESS_END')
)

FR2_SYS1_COMPARATOR_INPUTS = dict(
    field_switch={'word': 'item', 'wordno': 'itemno','stim_list': 'stimList', 'is_stim': 'isStim'},
    field_ignore=all_ignore + (
                  'stimAnode', 'stimAnodeTag',
                  'stimCathode', 'stimCathodeTag',
                  'stimAmp', 'stimLoc'),
    exceptions=fr2_comparison_exceptions,
    type_ignore=('INSTRUCT_START', 'INSTRUCT_END',
                 'PRACTICE_REC_START', 'PRACTICE_REC_END',
                 'SESSION_SKIPPED', 'INSTRUCT_VIDEO', 'STIM_OFF',
                 'B', 'E', 'SESS_END')
)

PAL3_COMPARATOR_INPUTS = dict(
    field_switch={'resp_pass': 'pass', 'stim_list': 'stimList', 'is_stim': 'isStim', 'stim_type': 'stimType'},
    field_ignore=all_ignore + ('stimLoc', 'stimAmp',
                  'stimAnode', 'stimAnodeTag', 'stimCathode',
                  'stimCathodeTag', 'stimTrial'),
    exceptions=pal_comparison_exceptions,
    type_ignore=('COUNTDOWN_START', 'COUNTDOWN_END', 'B', 'E', 'STIM_PARAMS', 'REC_END', 'SESS_START',
                 'MIC_TEST', 'PRACTICE_PAIR_OFF',
                 'INSTRUCT_VIDEO_ON','INSTRUCT_VIDEO_OFF',
                 'FEEDBACK_SHOW_ALL_PAIRS', 'SESSION_SKIPPED')
)

PAL1_SYS1_COMPARATOR_INPUTS = dict(
    field_switch={'resp_pass': 'pass', 'is_stim': 'isStim', 'stim_list': 'stimTrial', 'stim_type': 'stimType',},
    field_ignore=all_ignore + ('stimLoc', 'stimAmp',
                  'stimAnode', 'stimAnodeTag', 'stimCathode',
                  'stimCathodeTag'),
    exceptions=pal_comparison_exceptions,
    type_ignore=('COUNTDOWN_START', 'COUNTDOWN_END', 'B', 'E', 'STIM_PARAMS', 'REC_END', 'SESS_START',
                 'MIC_TEST', 'PRACTICE_PAIR_OFF',
                 'INSTRUCT_VIDEO_ON','INSTRUCT_VIDEO_OFF',
                 'FEEDBACK_SHOW_ALL_PAIRS', 'SESSION_SKIPPED')
)

PAL1_SYS2_COMPARATOR_INPUTS = dict(
    field_switch={'resp_pass': 'pass', 'stim_list': 'stimTrial', 'is_stim': 'isStim', 'stim_type': 'stimType'},
    field_ignore=all_ignore + ('stimLoc', 'stimAmp',
                  'stimAnode', 'stimAnodeTag', 'stimCathode',
                  'stimCathodeTag', 'isStimList', 'stimList'),
    exceptions=pal_comparison_exceptions,
    type_ignore=('COUNTDOWN_START', 'COUNTDOWN_END', 'B', 'E', 'STIM_PARAMS', 'REC_END', 'SESS_START',
                 'MIC_TEST', 'PRACTICE_PAIR_OFF',
                 'INSTRUCT_VIDEO_ON','INSTRUCT_VIDEO_OFF',
                 'FEEDBACK_SHOW_ALL_PAIRS', 'SESSION_SKIPPED')
)

PAL2_COMPARATOR_INPUTS = dict(
    field_switch={'resp_pass': 'pass', 'stim_list': 'stimTrial', 'stim_type': 'stimType', 'is_stim': 'isStim'},
    field_ignore=all_ignore + ('stimLoc', 'stimAmp',
                  'stimAnode', 'stimAnodeTag', 'stimCathode',
                  'stimCathodeTag'),
    exceptions=pal_comparison_exceptions,
    type_ignore=('COUNTDOWN_START', 'COUNTDOWN_END', 'B', 'E', 'STIM_PARAMS', 'REC_END', 'SESS_START',
                 'MIC_TEST', 'PRACTICE_PAIR_OFF',
                 'INSTRUCT_VIDEO_ON','INSTRUCT_VIDEO_OFF',
                 'FEEDBACK_SHOW_ALL_PAIRS', 'SESSION_SKIPPED')
)

CATFR_SYS1_COMPARATOR_INPUTS = dict(
    field_switch={'word': 'item', 'wordno': 'itemno', 'stim_list': 'stimList',
                  'category_num': 'categoryNum', 'is_stim': 'isStim'},
    field_ignore=all_ignore + ('stimAnode', 'stimAnodeTag',
                  'stimCathode', 'stimCathodeTag', 'stimAmp'),
    exceptions=catfr_comparison_exceptions,
    type_ignore=('INSTRUCT_START', 'INSTRUCT_END',
                 'SESSION_SKIPPED', 'INSTRUCT_VIDEO', 'STIM_OFF', 'STIM_PARAMS',
                 'B', 'E', 'COUNTDOWN_START', 'SESS_END', 'PRACTICE_REC_START', 'PRACTICE_REC_END')
)
SYS2_COMPARATOR_INPUTS = dict(
    FR3=FR3_SYS2_COMPARATOR_INPUTS,
    FR1=FR1_SYS2_COMPARATOR_INPUTS,
    PAL1=PAL1_SYS2_COMPARATOR_INPUTS,
    catFR1=CATFR_SYS1_COMPARATOR_INPUTS,
    PAL3=PAL3_COMPARATOR_INPUTS,
    PS=PS_SYS2_COMPARATOR_INPUTS

)

SYS1_COMPARATOR_INPUTS = dict(
    FR1=FR1_SYS1_COMPARATOR_INPUTS,
    FR2=FR2_SYS1_COMPARATOR_INPUTS,
    PAL1=PAL1_SYS1_COMPARATOR_INPUTS,
    PAL2=PAL2_COMPARATOR_INPUTS,
    catFR1=CATFR_SYS1_COMPARATOR_INPUTS,
    catFR2=CATFR_SYS1_COMPARATOR_INPUTS,
    PS=PS_COMPARATOR_INPUTS
)

SYS1_STIM_COMPARISON_INPUTS = dict(
    FR1=FR1_STIM_COMPARISON,
    FR2=FR2_STIM_COMPARISON,
    FR3=FR3_STIM_COMPARISON,
    catFR1=CATFR_STIM_COMPARISON,
    catFR2=CATFR_STIM_COMPARISON,
    PAL1=PAL_STIM_COMPARISON,
    PAL2=PAL_STIM_COMPARISON,
    PAL3=PAL3_STIM_COMPARISON,
    PS=PS_SYS1_STIM_COMPARISON
)

SYS2_STIM_COMPARISON_INPUTS = dict(
    FR1=FR1_STIM_COMPARISON,
    FR2=FR2_STIM_COMPARISON,
    FR3=FR3_STIM_COMPARISON,
    catFR1=CATFR_STIM_COMPARISON,
    catFR2=CATFR_STIM_COMPARISON,
    PAL1=PAL_STIM_COMPARISON,
    PAL2=PAL_STIM_COMPARISON,
    PAL3=PAL3_STIM_COMPARISON,
    PS=PS_SYS2_STIM_COMPARISON
)

def check_sys2_sessions(session_list, experiment):
    for subject, session in session_list:
        yield check_event_creation, subject, experiment, session, True, SYS2_COMPARATOR_INPUTS[experiment]

def check_sys1_sessions(session_list, experiment):
    for subject, session, eeg_pulse_file in session_list:
        task_pulse_path = os.path.join(DATA_ROOT, subject, 'behavioral', experiment, 'session_%d' % session, 'eeg.eeglog')
        eeg_pulse_path = os.path.join(DATA_ROOT, subject, 'eeg.noreref', eeg_pulse_file)
        eeg_stem = os.path.join(DATA_ROOT, subject, 'eeg.noreref', eeg_pulse_file.split('.')[0])

        yield check_event_creation, subject, experiment, session, False, SYS1_COMPARATOR_INPUTS[experiment], \
              task_pulse_path, eeg_pulse_path, eeg_stem

def xtest_fr3_event_creation():
    for test in check_sys2_sessions(FR3_SESSIONS, 'FR3'):
        yield test

def xtest_fr1_sys2_event_creation():
    for test in check_sys2_sessions(FR1_SYS2_SESSIONS, 'FR1'):
        yield test

def xtest_fr1_sys1_event_creation():
    for test in check_sys1_sessions(FR1_SYS1_SESSIONS, 'FR1'):
        yield test

def xtest_fr2_event_creation():
    for test in check_sys1_sessions(FR2_SESSIONS, 'FR2'):
        yield test

def xtest_pal1_sys1_event_creation():
    for test in check_sys1_sessions(PAL1_SYS1_SESSIONS, 'PAL1'):
        yield test

def xtest_pal1_sys2_event_creation():
    for test in check_sys2_sessions(PAL1_SYS2_SESSIONS, 'PAL1'):
        yield test

def xtest_catfr1_sys1_event_creation():
    for test in check_sys1_sessions(CATFR1_SYS1_SESSIONS, 'catFR1'):
        yield test

def test_catfr1_sys2_event_creation():
    for test in check_sys2_sessions(CATFR1_SYS2_SESSIONS, 'catFR1'):
        yield test

def test_catfr2_event_creation():
    for test in check_sys1_sessions(CATFR2_SESSIONS, 'catFR2'):
        yield test



def xtest_math_event_creation():

    def exceptions(event1, event2, field, parent_field=None):
        if field == 'test' and event1['test'].split(';') == event2['test']:
            return True
        if field == 'test':
            return True
        return False

    def persistent_field_fn(event):
        if event['type']=='WORD':
            return ('list', 'serialpos', 'word', 'wordno', 'recalled',
                    'intrusion', 'stimList', 'subject', 'session', 'eegfile',
                     'rectime')
        else:
            return ('list', 'serialpos', 'stimList', 'subject', 'session', 'eegfile', 'rectime')

    for subject, session in PAL1_SYS1_SESSIONS:
        print 'Processing %s:%d' % (subject, session)
        math_parser = math_parser_wrapper(subject, session, 'PAL2', base_dir=DATA_ROOT)
        py_events = math_parser.parse()


        mat_fr3_events_reader = \
            BaseEventReader(
                    filename=os.path.join(DATA_ROOT, subject, 'behavioral', 'PAL2', 'session_%d' % session,
                                          'MATH_events.mat'),
                    common_root=DATA_ROOT)

        print 'Loading mat_events for %s:%d' % (subject, session)
        mat_events = mat_fr3_events_reader.read()

        comparator = EventComparator(py_events, mat_events,
                                     field_ignore=('eegfile', 'eegoffset'),
                                     type_ignore=('COUNTDOWN_START', 'COUNTDOWN_END', 'B', 'E', 'STIM_PARAMS'),
                                     exceptions=exceptions
                                     )
        print 'Verifying %s:%d' % (subject, session)
        found_bad, err_msg = comparator.compare()

        assert found_bad is False, err_msg


def xtest_ltpfr_event_creation():

    def exceptions(event1, event2, field, parent_field=None):
        if field == 'recalled' and event1['recalled'] == False and event2['recalled'] == -999:
            return True
        if field == 'list' and event1['list'] == -1 and event2['list'] == -999:
            return True
        if field == 'wordno' and event1['list'] == -1:
            return True
        if field == 'type' and event1['field'] == 'INSTRUCT_START':
            return True
        if field == 'type' and event1['type'] == 'PRACTICE_WORD_OFF':
            return True
        if field == 'serialpos' and event1['list'] == -1:
            return True
        if field == 'word' and event1['list'] == -1:
            return True
        if (field in ['word', 'wordno', 'serialpos', 'rectime', 'recalled']) and event1['type'] == 'WORD_OFF':
            return True
        if field == 'msoffset' and event1['type'] == 'REC_START':
            return True
        if field in ('expVersion', 'serialPos', 'recalled', 'msoffset') and event1['type'] == 'REC_WORD':
            return True
        if field == 'serialpos' and event1['type'] == 'REC_WORD':
            return True
        if field in ('wordno', 'intrusion', 'msoffset', 'mstime') and event1['type'] == 'REC_WORD_VV':
            return True
        if field == 'rectime' and np.abs(event1['rectime'] - event2['rectime']) <= 1:
            return True
        if field == 'mstime' and np.abs(event1['mstime'] - event2['mstime']) <= 1.5:
            return True
        if field == 'wordno' and event1['type'] == 'REC_WORD' and event1['intrusion'] == -1:
            return True
        if field == 'eegoffset' and abs(event1['eegoffset'] - event2['eegoffset']) <= 5:
            return True
        if field == 'msoffset' and event1['type'] == 'STIM':
            return True
        if field == 'stim_list' and event1['stim_list'] == False and event2['stim_list'] == -999:
            return True
        if field == 'stim_list' and event1['type'] in ('REC_START', 'REC_WORD', 'REC_WORD_VV') and event1['stim_list'] == True:
            return True
        if field in ('wordno', 'word', 'serialpos') and event1['type'] == 'STIM' and event2['wordno'] == -999:
            return True
        if field is None and event2 is None and event1['type'] == 'STIM' and event1['eegoffset'] == -1:
            return True
        if field == 'is_stim' and event1['is_stim'] == False and event2['is_stim'] == -999:
            return True
        if parent_field == 'stimParams' and event1['type'] != 'STIM' and event1['type'] != 'STIM_OFF':
            return True
        return False

    def persistent_field_fn(event):
        if event['type']=='WORD':
            return ('list', 'serialpos', 'word', 'wordno', 'recalled',
                    'intrusion', 'stim_list', 'subject', 'session', 'eegfile',
                     'rectime')
        else:
            return ('list', 'serialpos', 'stim_list', 'subject', 'session', 'eegfile', 'rectime')

    for subject, session in LTPFR_SESSIONS:
        print 'Processing %s:%d' % (subject, session)
        ltpFR_parser = ltpfr_log_parser_wrapper(subject, session, '', base_dir=DATA_ROOT)
        py_events = ltpFR_parser.parse()

        mat_ltpfr_events_reader = \
            BaseEventReader(
                    filename=os.path.join(DATA_ROOT, subject, 'session_%d' % session,
                                          'events.mat'),
                    common_root=DATA_ROOT)

        print 'Loading mat_events for %s:%d' % (subject, session)
        mat_events = mat_ltpfr_events_reader.read()

        comparator = EventComparator(py_events, mat_events,
                                     field_switch={'word': 'item', 'wordno': 'itemno'},
                                     field_ignore=('eegfile', 'eegoffset', 'expVersion', 'stimAnode', 'stimAnodeTag',
                                                   'stimCathode', 'stimCathodeTag', 'stimAmp'),
                                     exceptions=exceptions,
                                     type_ignore=('INSTRUCT_START', 'INSTRUCT_END',
                                      'PRACTICE_REC_START', 'PRACTICE_REC_END',
                                      'SESSION_SKIPPED', 'INSTRUCT_VIDEO','STIM_OFF')
                                     )
        print 'Verifying %s:%d' % (subject, session)
        found_bad, err_msg = comparator.compare()

        assert found_bad is False, err_msg



def test_to_json():

    def persistent_field_fn(event):
        if event['type']=='WORD':
            return ('list', 'serialpos', 'word', 'wordno', 'recalled',
                    'intrusion', 'stim_list', 'subject', 'session', 'eegfile',
                     'rectime')
        else:
            return ('list', 'serialpos', 'stim_list', 'subject', 'session', 'eegfile', 'rectime')

    subject = 'R1163T'
    session = 0
    FR_parser = fr_log_parser_wrapper(subject, session, 'FR3', base_dir=DATA_ROOT)
    aligner = System2Aligner(subject, 'FR3', session, FR_parser.parse(),  False, DATA_ROOT)
    aligner.add_stim_events(FR_parser.event_template, persistent_field_fn)
    py_events = aligner.align('SESS_START')
    print(to_json(py_events))

def xtest_from_json():
    def persistent_field_fn(event):
        if event['type']=='WORD':
            return ('list', 'serialpos', 'word', 'wordno', 'recalled',
                    'intrusion', 'stim_list', 'subject', 'session', 'eegfile',
                     'rectime')
        else:
            return ('list', 'serialpos', 'stim_list', 'subject', 'session', 'eegfile', 'rectime')

    subject = 'R1163T'
    session = 0;
    FR_parser = fr_log_parser_wrapper(subject, session, 'FR3', base_dir=DATA_ROOT)
    aligner = System2Aligner(subject, 'FR3', session, FR_parser.parse(),  False, DATA_ROOT)
    aligner.add_stim_events(FR_parser.event_template, persistent_field_fn)
    py_events = aligner.align('SESS_START')
    to_json(py_events, open('test_file.json', 'w'))
    arr = from_json('test_file.json')

    #for key in df:
    #    if type(df[key][0] == dict):
    #        arr[key] = pd.DataFrame(arr[key].tolist()).to_records(False)

    pprint_rec(arr)

    comparator = EventComparator(py_events, arr)
    found_bad, error_msg = comparator.compare()
    assert found_bad is False, error_msg

def xtest_read_json():
    import json
    from viewers.view_recarray import mkdtype, copy_values
    d = json.load(open('test_file.json'))
    dt = mkdtype(d[0])
    arr = np.zeros(len(d), dt)
    copy_values(d, arr)
    pprint_rec(arr[0])
    pprint_rec(arr)

