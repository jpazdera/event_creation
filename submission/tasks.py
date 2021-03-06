import os
import glob
import re
import json
import datetime

from parsers.pal_log_parser import PALSessionLogParser
from alignment.system1 import System1Aligner
from alignment.system2 import System2Aligner
from readers.eeg_reader import get_eeg_reader
from viewers.view_recarray import to_json, from_json
from parsers.fr_log_parser import FRSessionLogParser
from parsers.catfr_log_parser import CatFRSessionLogParser
from parsers.math_parser import MathSessionLogParser
from parsers.base_log_parser import EventComparator
from parsers.ps_log_parser import PSLogParser
from parsers.base_log_parser import StimComparator
from loggers import log, logger
from transferer import DATA_ROOT, DB_ROOT

from tests.test_event_creation import SYS1_COMPARATOR_INPUTS, SYS2_COMPARATOR_INPUTS, \
    SYS1_STIM_COMPARISON_INPUTS, SYS2_STIM_COMPARISON_INPUTS


try:
    from ptsa.data.readers.BaseEventReader import BaseEventReader
    PTSA_LOADED = True
except:
    log('PTSA NOT LOADED')
    PTSA_LOADED = False

class SplitEEGTask(object):

    SPLIT_FILENAME = '{subject}_{experiment}_{session}_{time}'

    def __init__(self, subject, montage, experiment, session, **kwargs):
        self.name = 'Splitting {subj} {exp}_{sess}'.format(subj=subject, exp=experiment, sess=session)
        self.subject = subject
        self.experiment = experiment
        self.session = session
        self.kwargs = kwargs

    def set_pipeline(self, pipeline):
        self.pipeline = pipeline

    @staticmethod
    def group_ns2_files(raw_eegs):
        raw_eeg_groups = []
        for raw_eeg in raw_eegs:
            for group in raw_eeg_groups:
                if raw_eeg.replace('np1', 'np2') == group[0].replace('np1', 'np2'):
                    group.append(raw_eeg)
                    break
            else:
                raw_eeg_groups.append([raw_eeg])
        raw_eeg_groups = [group[0] if len(group) == 1 else group for group in raw_eeg_groups]
        return raw_eeg_groups


    def run(self, files, db_folder):
        logger.set_label(self.name)
        raw_eegs = files['raw_eeg']
        if not isinstance(raw_eegs, list):
            raw_eegs = [raw_eegs]

        raw_eeg_groups = self.group_ns2_files(raw_eegs)

        for raw_eeg in raw_eeg_groups:
            if 'substitute_raw_file_for_header' in files:
                reader = get_eeg_reader(raw_eeg,
                                       files['jacksheet'],
                                       substitute_raw_file_for_header=files['substitute_raw_file_for_header'])
            else:
                try:
                    reader = get_eeg_reader(raw_eeg,
                                            files['jacksheet'])
                except KeyError as k:
                    log('Cannot split file with extension {}'.format(k), 'WARNING')
                    continue

            split_eeg_filename = self.SPLIT_FILENAME.format(subject=self.subject,
                                                            experiment=self.experiment,
                                                            session=self.session,
                                                            time=reader.get_start_time_string())
            reader.split_data(self.pipeline.destination, split_eeg_filename)
        num_split_files = len(glob.glob(os.path.join(self.pipeline.destination, 'noreref', '*.[0-9]*')))
        if num_split_files == 0:
            raise UnProcessableException(
                'Seems like splitting did not properly occur. No split files found in {}. Check jacksheet'.format(self.pipeline.destination))

class EventCreationTask(object):

    PARSERS = {
        'FR': FRSessionLogParser,
        'PAL': PALSessionLogParser,
        'catFR': CatFRSessionLogParser,
        'math': MathSessionLogParser,
        'PS': PSLogParser
    }

    def __init__(self, protocol, subject, montage, experiment, session, is_sys2, event_label='task', parser_type=None, **kwargs):
        self.name = '{label} Event Creation for {subj}: {exp}_{sess}'.format(label=event_label, subj=subject, exp=experiment, sess=session)
        self.parser_type = parser_type or self.PARSERS[re.sub(r'\d', '', experiment)]
        self.protocol = protocol
        self.subject = subject
        self.montage = montage
        self.experiment = experiment
        self.session = session
        self.is_sys2 = is_sys2
        self.kwargs = kwargs
        self.event_label = event_label
        self.filename = '{label}_events.json'.format(label=event_label)
        self.pipeline = None

    def set_pipeline(self, pipeline):
        self.pipeline = pipeline

    def run(self, files, db_folder):
        logger.set_label(self.name)
        parser = self.parser_type(self.protocol, self.subject, self.montage, self.experiment, files)
        unaligned_events = parser.parse()
        if self.is_sys2:
            aligner = System2Aligner(unaligned_events, files, db_folder)
            if self.event_label != 'math':
                aligner.add_stim_events(parser.event_template, parser.persist_fields_during_stim)
            events = aligner.align('SESS_START')
        else:
            aligner = System1Aligner(unaligned_events, files)
            events = aligner.align()
        events = parser.clean_events(events)
        with open(os.path.join(self.pipeline.destination, self.filename), 'w') as f:
            to_json(events, f)

class AggregatorTask(object):

    def __init__(self, subject, montage, experiment, session, protocol='r1', code=None):
        self.name = 'Aggregation of {subj}: {exp}_{sess}'.format(subj=subject, exp=experiment, sess=session)
        self.subject, self.montage, self.experiment, self.session, self.protocol =\
            subject, montage, experiment, session, protocol
        self.code = code or subject
        self.pipeline = None
        self.protocol_folder = os.path.join(DB_ROOT, 'protocols', self.protocol)
        if not os.path.exists(self.protocol_folder):
            os.makedirs(self.protocol_folder)

        self.montages_folder = os.path.join(DB_ROOT, 'protocols', self.protocol, 'montages', self.code)
        if not os.path.exists(self.montages_folder):
            os.makedirs(self.montages_folder)

    def set_pipeline(self, pipeline):
        self.pipeline = pipeline

    def build_experiments_aggregate(self):
        experiments_aggregate = os.path.join(self.protocol_folder, 'experiments.json')
        if os.path.exists(experiments_aggregate):
            experiments = json.load(open(experiments_aggregate))
        else:
            experiments = {}
        if self.experiment not in experiments:
            experiments[self.experiment] = {}
        if self.subject not in experiments[self.experiment]:
            experiments[self.experiment][self.subject] = []
        if self.session not in experiments[self.experiment][self.subject]:
            experiments[self.experiment][self.subject].append(self.session)

        with open(experiments_aggregate, 'w') as experiment_output:
            json.dump(experiments, experiment_output, indent=2, sort_keys=True)

    def build_sessions_aggregate(self):
        code_aggregate = os.path.join(self.montages_folder, 'sessions.json')
        if os.path.exists(code_aggregate):
            sessions = json.load(open(code_aggregate))
        else:
            sessions = {}

        if self.experiment not in sessions:
            sessions[self.experiment] = {}
        sessions[self.experiment][self.session] = {'montage': self.montage,
                                                   'submitted': datetime.datetime.now().strftime('%Y-%m-%d')}

        with open(code_aggregate, 'w') as code_output:
            json.dump(sessions, code_output, indent=2)

    def build_code_info_aggregate(self):
        info_aggregate = os.path.join(self.montages_folder, 'info.json')
        if os.path.exists(info_aggregate):
            info = json.load(open(info_aggregate))
            if float(info['montage']) != float(self.montage):
                raise UnProcessableException('Montage number conflicts for subject {}. Existing: {}, new: {}'.format(
                    self.subject, info['montage'], self.montage
                ))
            return
        else:
            info = {}

        info['montage'] = self.montage
        info['submitted'] = datetime.datetime.now().strftime('%Y-%m-%d')

        with open(info_aggregate, 'w') as info_output:
            json.dump(info, info_output, indent=2)

    def run(self, files, db_folder):
        logger.set_label(self.name)
        log('Building experiments aggregate')
        self.build_experiments_aggregate()
        log('Building codes aggregate')
        self.build_code_info_aggregate()

class CompareEventsTask(object):

    def __init__(self, subject, montage, experiment, session, protocol='r1', code=None, original_session=None):
        self.name = 'Comparator {}: {}_{}'.format(subject, experiment, session)
        self.subject = subject
        self.code = code if code else subject
        self.original_session = original_session if not original_session is None else session
        self.montage = montage
        self.experiment = experiment
        self.session = session
        self.protocol = protocol

    def set_pipeline(self, pipeline):
        self.pipeline = pipeline

    def run(self, files, db_folder):
        logger.set_label(self.name)
        mat_events_reader = \
            BaseEventReader(
                filename=os.path.join(DATA_ROOT, '..', 'events', 'RAM_{}'.format(self.experiment[0].upper() + self.experiment[1:]),
                                      '{}_events.mat'.format(self.code)),
                common_root=DATA_ROOT,
                eliminate_events_with_no_eeg=False,
            )
        log('Loading matlab events')
        mat_events = mat_events_reader.read()
        self.sess_mat_events = mat_events[mat_events.session == self.original_session]
        if not PTSA_LOADED:
            raise UnProcessableException('Cannot compare events without PTSA')
        new_events = from_json(os.path.join(db_folder, 'task_events.json'))
        major_version = '.'.join(new_events[-1].exp_version.split('.')[:1])

        if float(major_version.split('_')[-1]) >= 2:
            comparator_inputs = SYS2_COMPARATOR_INPUTS[self.experiment]
        else:
            comparator_inputs = SYS1_COMPARATOR_INPUTS[self.experiment]
        comparator = EventComparator(new_events, self.sess_mat_events, **comparator_inputs)
        log('Comparing events...')

        found_bad, error_message = comparator.compare()

        if found_bad is True:
            assert False, error_message
        else:
            log('Comparison Success!')

        log('Comparing stim events...')


        if float(major_version.split('_')[-1]) >= 2:
            comparator_inputs = SYS2_STIM_COMPARISON_INPUTS[self.experiment]
        else:
            comparator_inputs = SYS1_STIM_COMPARISON_INPUTS[self.experiment]

        stim_comparator = StimComparator(new_events, self.sess_mat_events, **comparator_inputs)
        errors = stim_comparator.compare()

        if errors:
            assert False, errors
        else:
            log('Stim comparison success!')







class UnProcessableException(Exception):
    pass

def change_current(source_folder, *args):
    destination_directory = os.path.join(DB_ROOT, *args)
    destination_source = os.path.join(destination_directory, source_folder)
    destination_processed = os.path.join(destination_directory, '{}_processed'.format(source_folder))
    if not os.path.exists(destination_source):
        raise UnProcessableException('Source folder {} does not exist'.format(destination_source))
    if not os.path.exists(destination_processed):
        raise UnProcessableException('Processed folder {} does not exist'.format(destination_processed))

    current_source = os.path.join(destination_directory, 'current_source')
    current_processed = os.path.join(destination_directory, 'current_processed')

    previous_current_source = os.path.basename(os.path.realpath(current_source))

    log('Unlinking current source: {}'.format(os.path.realpath(current_source)))
    os.unlink(current_source)
    try:
        log('Linking current source to {}'.format(source_folder))
        os.symlink(source_folder, current_source)
    except Exception as e:
        log('ERROR {}. Rolling back'.format(e.message))
        os.symlink(previous_current_source, current_source)
        raise

    previous_current_processed = os.path.basename(os.path.realpath(current_processed))
    try:
        log('Unlinking current processed: {}'.format(os.path.realpath(current_processed)))
        os.unlink(current_processed)
    except Exception as e:
        log('ERROR {}. Rolling back'.format(e.message))
        os.symlink(previous_current_source, current_source)

    try:
        processed_folder = '{}_processed'.format(source_folder)
        log('Linking current processed to {}'.format(processed_folder))
        os.symlink(processed_folder, current_processed)
    except Exception as e:
        log('ERROR {}. Rolling back'.format(e.message))
        os.symlink(previous_current_source, current_source)
        os.symlink(previous_current_processed, current_processed)

def test_change_current():
    from convenience import build_split_pipeline
    import time
    subject, montage, experiment, session, protocol = 'R1001P', '0.0', 'FR1', 0, 'r1',
    pipeline_1 = build_split_pipeline(subject, montage, experiment, session)
    pipeline_1.run()
    previous_label = pipeline_1.source_label
    time.sleep(5)
    pipeline_2 = build_split_pipeline(subject, montage, experiment, session)
    pipeline_2.run(force=True)
    change_current(previous_label,
                            'protocols', protocol,
                            'subjects', subject,
                            'experiments', experiment,
                            'sessions', str(session),
                            'ephys')

