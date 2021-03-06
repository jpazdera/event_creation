import re
import os
import json
import glob
import numpy as np
import sys
import argparse

from transferer import generate_ephys_transferer, generate_session_transferer, TransferPipeline
from tasks import SplitEEGTask, EventCreationTask, AggregatorTask, CompareEventsTask
from transferer import DB_ROOT, DATA_ROOT
from loggers import log, logger

from parsers.math_parser import MathSessionLogParser

try:
    from ptsa.data.readers.BaseEventReader import BaseEventReader
    PTSA_LOADED=True
except:
    log('PTSA NOT LOADED')
    PTSA_LOADED=False

GROUPS = {
    'FR': ('verbal', 'stim'),
    'PAL': ('verbal', 'stim'),
    'catFR': ('verbal', 'stim'),
    'PS': ('stim',)
}

class UnknownMontageException(Exception):
    pass

def build_split_pipeline(subject, montage, experiment, session, protocol='r1', groups=tuple(), code=None,
                         original_session=None, new_experiment=None, **kwargs):
    new_experiment = new_experiment if not new_experiment is None else experiment
    transferer = generate_ephys_transferer(subject, experiment, session, protocol, groups,
                                           code=code,
                                           original_session=original_session,
                                           new_experiment=new_experiment,
                                           **kwargs)
    task = SplitEEGTask(subject, montage, experiment, session, **kwargs)
    return TransferPipeline(transferer, task)

def build_events_pipeline(subject, montage, experiment, session, do_math=True, protocol='r1', code=None,
                          groups=tuple(), do_compare=False, **kwargs):
    exp_type = re.sub('\d','', experiment)
    if exp_type in GROUPS:
        groups += GROUPS[exp_type]
    groups += (exp_type,)

    transferer, groups = generate_session_transferer(subject, experiment, session, protocol, groups, code=code, **kwargs)
    tasks = [EventCreationTask(protocol, subject, montage, experiment, session, 'system_2' in groups)]
    if do_math:
        tasks.append(EventCreationTask(protocol, subject, montage, experiment, session, 'system_2' in groups, 'math', MathSessionLogParser))
    if do_compare:
        tasks.append(CompareEventsTask(subject, montage, experiment, session, protocol, code,
                                       kwargs['original_session'] if 'original_session' in kwargs else None))

    tasks.append(AggregatorTask(subject, montage, experiment, session, protocol, code))
    return TransferPipeline(transferer, *tasks)

def determine_montage_from_code(code, protocol='r1', allow_new=False, allow_skip=False):
    montage_file = os.path.join(DB_ROOT, 'protocols', protocol, 'montages', code, 'info.json')
    if os.path.exists(montage_file):
        info = json.load(open(montage_file))
        return info['montage']
    elif '_' not in code:
        return '0.0'
    elif not allow_new:
        raise UnknownMontageException('Could not determine montage for {}'.format(code))
    else:
        montage_code = int(code.split('_')[1])
        ref_localized_file = os.path.join(DATA_ROOT, code, 'ref_localized.txt')
        if os.path.exists(ref_localized_file):
            ref_localized_subj = open(ref_localized_file).read()
            ref_montage = determine_montage_from_code(ref_localized_subj, protocol, allow_new, False)
            new_montage_num = float(ref_montage) + .1
        else:
            subj_code = code.split('_')[0]
            if montage_code == 0:
                return '0.0'
            ref_montage = determine_montage_from_code('{}_{}'.format(subj_code, montage_code-1), protocol, True, False)
            new_montage_num = (float(ref_montage) + 1.1)

        if new_montage_num % 1 > montage_code:
            raise Exception('Could not allocate new montage number with existing montage {} and code {}'.format(
                ref_montage, code))
        elif round((new_montage_num % 1) * 10) < montage_code:
            if allow_skip:
                log('Warning: Skipping montages from {} to {}'.format(new_montage_num, montage_code))
                return '%d.%d' % (int(new_montage_num), montage_code)
            else:
                raise Exception('Montage creation error: montages {} to {} do not exist'.format((new_montage_num%1)*10,
                                                                                                montage_code))

        return '%1.1f' % (new_montage_num)


def get_subject_sessions_by_experiment(experiment, protocol='r1'):
    if re.match('catFR[0-4]', experiment):
        ram_exp = 'RAM_{}'.format(experiment[0].capitalize() + experiment[1:])
    else:
        ram_exp = 'RAM_{}'.format(experiment)
    events_dir = os.path.join(DATA_ROOT, '..', 'events', ram_exp)
    events_files = sorted(glob.glob(os.path.join(events_dir, '{}*_events.mat'.format(protocol.upper()))))
    for events_file in events_files:
        subject = '_'.join(os.path.basename(events_file).split('_')[:-1])
        if '_' in subject:
            continue
        mat_events_reader = BaseEventReader(filename=events_file, common_root=DATA_ROOT)
        log('Loading matlab events {exp}: {subj}'.format(exp=experiment, subj=subject))
        try:
            mat_events = mat_events_reader.read()
            yield (subject, np.unique(mat_events['session']))
        except AttributeError:
            log('Failed.')

def get_first_unused_session(subject, experiment, protocol='r1'):
    sessions_dir = os.path.join(DB_ROOT,
                               'protocols', protocol,
                               'subjects', subject,
                               'experiments', experiment,
                               'sessions')
    if not os.path.exists(sessions_dir):
        return 0
    session_folders = os.listdir(sessions_dir)
    session_folders_with_behavioral = [folder for folder in session_folders
                                       if os.path.isdir(os.path.join(sessions_dir, folder)) and
                                       'behavioral' in os.listdir(os.path.join(sessions_dir, folder))]
    session_folders_with_current = [folder for folder in session_folders_with_behavioral
                                    if 'current_processed' in os.listdir(os.path.join(sessions_dir, folder, 'behavioral'))]
    session_numbers = [int(sess) for sess in session_folders_with_current if sess.isdigit()]
    if session_numbers:
        return max(session_numbers) + 1
    else:
        return 0

def run_individual_pipline(pipeline_fn, kwargs, force_run=False):
    pipeline = pipeline_fn(**kwargs)
    pipeline.run(force_run)

def check_subject_sessions(code, experiment, sessions, protocol='r1'):
    bad_sessions = json.load(open(BAD_EXPERIMENTS_FILE))
    subject = re.sub(r'_.*', '', code)
    montage = determine_montage_from_code(code, allow_new=True, allow_skip=True)
    test_inputs = dict(
        subject = subject,
        montage = montage,
        experiment = experiment,
        force = False,
        do_compare = True,
        code = code
    )
    sessions = sorted(sessions)
    for session in sessions:
        if subject in bad_sessions and \
                        experiment in bad_sessions[subject] and \
                        str(session) in bad_sessions[subject][experiment]:
            log('SKIPPING {} {}_{}: {}'.format(subject, experiment, session,
                                               bad_sessions[subject][experiment][str(session)]))
            continue

        test_inputs['original_session'] = session
        if '_' in code:
            test_inputs['session'] = get_first_unused_session(subject, experiment, protocol)
        else:
            test_inputs['session'] = session

        if test_inputs['session'] != test_inputs['original_session']:
            log('Warning: {subj} {exp}_{orig_sess} -> {code} {exp}_{sess}'.format(subj=subject,
                                                                                  code=code,
                                                                                  sess=session,
                                                                                  exp=experiment,
                                                                                  orig_sess=test_inputs['session']))
        yield run_individual_pipline, build_split_pipeline, test_inputs
        yield run_individual_pipline, build_events_pipeline, test_inputs, False

def check_experiment(experiment):
    experiment_sessions = get_subject_sessions_by_experiment(experiment)
    for subject, sessions in experiment_sessions:
        for test in check_subject_sessions(subject, experiment, sessions):
            yield test

BAD_EXPERIMENTS_FILE = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'unrecoverable_sessions.json')

EXPERIMENTS = ('FR1', 'FR2', 'FR3', 'PAL1', 'PAL2', 'PAL3', 'catFR1', 'catFR2', 'catFR3')

def clean_db_dir(db_dir):
    for root, dirs, files in os.walk(db_dir, False):
        if len(dirs) == 0 and len(files) == 1 and 'log.txt' in files:
            os.remove(os.path.join(root, 'log.txt'))

def test_custom_imports():
    for test in run_from_json_file('custom_sessions.json'):
        yield test

def test_ps_sessions():
    for test in run_from_json_file('ps_sessions.json'):
        yield test

def test_all_experiments():
    logger.add_log_files(os.path.join(DB_ROOT, 'protocols', 'log.txt'))
    for experiment in EXPERIMENTS:
        for test in check_experiment(experiment):
            yield test

def xtest_fr2():
    logger.add_log_files(os.path.join(DB_ROOT, 'protocols', 'log.txt'))
    for test in check_experiment('FR2'):
        yield test


def xtest_fr1():
    logger.add_log_files(os.path.join(DB_ROOT, 'protocols', 'log.txt'))
    for test in check_experiment('FR1'):
        yield test


def xtest_fr3():
    logger.add_log_files(os.path.join(DB_ROOT, 'protocols', 'log.txt'))
    for test in check_experiment('FR3'):
        yield test

def xtest_pal1():
    logger.add_log_files(os.path.join(DB_ROOT, 'protocols', 'log.txt'))
    for test in check_experiment('PAL1'):
        yield test

def xtest_pal2():
    logger.add_log_files(os.path.join(DB_ROOT, 'protocols', 'log.txt'))
    for test in check_experiment('PAL2'):
        yield test

def xtest_pal3():
    logger.add_log_files(os.path.join(DB_ROOT, 'protocols', 'log.txt'))
    for test in check_experiment('PAL3'):
        yield test

def xtest_catfr1():
    logger.add_log_files(os.path.join(DB_ROOT, 'protocols', 'log.txt'))
    for test in check_experiment('catFR1'):
        yield test

def xtest_catfr2():
    logger.add_log_files(os.path.join(DB_ROOT, 'protocols', 'log.txt'))
    for test in check_experiment('catFR2'):
        yield test

def xtest_catfr3():
    logger.add_log_files(os.path.join(DB_ROOT, 'protocols', 'log.txt'))
    for test in check_experiment('catFR3'):
        yield test


def run_from_json_file(filename):
    bad_sessions = json.load(open(BAD_EXPERIMENTS_FILE))

    subjects = json.load(open(filename))
    sorted_subjects = sorted(subjects.keys())
    for subject in sorted_subjects:
        experiments = subjects[subject]
        for new_experiment in experiments:
            sessions = experiments[new_experiment]
            for session in sessions:
                if subject in bad_sessions and \
                                new_experiment in bad_sessions[subject] and \
                                str(session) in bad_sessions[subject][new_experiment]:
                    log('SKIPPING {} {}_{}: {}'.format(subject, new_experiment, session,
                                                       bad_sessions[subject][new_experiment][str(session)]))
                    continue
                info = sessions[session]
                experiment = info.get('original_experiment', new_experiment)
                original_session = info.get('original_session', session)
                is_sys1 = info.get('system_1', False)
                is_sys2 = info.get('system_2', False)
                montage = info.get('montage', 0.0)
                force = info.get('force', False)
                code = info.get('code', subject)

                inputs = dict(
                    subject = subject,
                    montage = montage,
                    experiment = experiment,
                    new_experiment = new_experiment,
                    force = force,
                    do_compare = True,
                    code=code,
                    session=session,
                    original_session=original_session,
                    groups = tuple()
                )

                raw_substitute = info.get('raw_substitute', False)
                if raw_substitute:
                    inputs['substitute_raw_folder'] = raw_substitute
                if is_sys1:
                    inputs['groups'] += ('system_1',)
                if is_sys2:
                    inputs['groups'] += ('system_2',)

                if 'PS' in experiment or 'TH' in experiment:
                    inputs['do_math'] = False

                yield run_individual_pipline, build_split_pipeline, inputs
                yield run_individual_pipline, build_events_pipeline, inputs, force




if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--from-file', dest='from_file', default=False,
                        help='process from file')
    parser.add_argument('--substitute-raw-for-header', dest='raw_header', action='store_true', default=False,
                        help='Signals input for raw folder with substitute header')
    parser.add_argument('--change-experiment', dest='new_exp', action='store_true', default=False,
                        help='Singals new experiment differs from old')
    parser.add_argument('--change-session', dest='new_session', action='store_true', default=False,
                        help='Signals new session number different than old')
    parser.add_argument('--sys2', dest='sys2', action='store_true', default=False,
                        help='Signals system 2 session')
    parser.add_argument('--sys1', dest='sys1', action='store_true', default=False,
                        help='Signals system 1 session')
    parser.add_argument('--force', dest='force', action='store_true', default=False,
                        help='Force creation even if no changes')
    args = parser.parse_args()
    if args.from_file:
        for test in run_from_json_file(args.from_file):
            test[0](*test[1:])
        sys.exit(0)

    code = raw_input('Enter subject code: ')
    subject = re.sub('_.*', '', code)
    original_experiment = raw_input('Enter original experiment: ')
    original_session = int(raw_input('Enter original session number: '))

    if subject != code:
        montage = raw_input('Enter montage #: ')
    else:
        montage = '0.0'
        session = original_session

    if args.new_session:
        session = int(raw_input('Enter new session number: '))
    else:
        session = original_session

    if args.new_exp:
        experiment = raw_input('Enter new experiment name: ')
    else:
        experiment = original_experiment

    inputs = dict(
        subject=subject,
        montage=montage,
        experiment=original_experiment,
        new_experiment=experiment,
        force=False,
        do_compare=True,
        code=code,
        session=session,
        original_session=original_session
    )


    if args.raw_header:
        header_substitute = raw_input('Enter raw folder containing substitute for header: ')
        inputs['substitute_raw_folder'] = header_substitute
    if args.sys2:
        inputs['groups'] = ('system_2',)
    if args.sys1:
        inputs['groups'] = ('system_1',)
    if args.force:
        inputs['force'] = True

    if 'PS' in experiment or 'TH' in experiment:
        inputs['do_math'] = False

    run_individual_pipline(build_split_pipeline, inputs)
    run_individual_pipline(build_events_pipeline, inputs)

