"""Shareable synthetic coverage fixture; no owner JD, résumé or private imports.

Two public optimizer test modules previously imported a private V3.3 test file.
This independently constructed portfolio preserves their coverage/breadth and
word-budget assertions without copying any of its experience claims.
"""
from copy import deepcopy
import re

REQUIREMENTS = {
    'rtest': 'Execute unit tests for software components',
    'rconfig': 'Use CI build automation',
    'rapi': 'Develop Python APIs',
    'rfrontend': 'Develop React user interfaces',
    'rdata': 'Use SQL database storage',
}


def evaluator(*, bullets, ranking_row):
    rules={'rtest':r'unit tests', 'rconfig':r'CI build automation',
           'rapi':r'Python API', 'rfrontend':r'React', 'rdata':r'SQL'}
    return [{'bullet_index':i,'bullet_text':text,
        'supported_requirement_ids':[identity for identity,phrase in rules.items() if re.search(phrase,text,re.I)]}
        for i,text in enumerate(bullets)]


def fixture():
    portfolios=[
        ('Synthetic report tool', ['Implemented unit tests and CI build automation for a synthetic command-line report processor.',
                                  'Recorded diagnostic messages for generated reports.', 'Documented sample report settings.'],
         ['Implemented unit tests and CI build automation.', 'Documented report settings.']),
        ('Synthetic service', ['Implemented Python API routes for a synthetic inventory service.',
                               'Added sample request validation messages.', 'Documented service configuration.'],
         ['Implemented Python API routes.', 'Documented service configuration.']),
        ('Synthetic interface', ['Implemented React screens for a synthetic inventory interface.',
                                 'Added keyboard navigation for example forms.'], ['Implemented React screens.']),
        ('Synthetic storage', ['Implemented SQL storage for a synthetic inventory example.',
                               'Documented sample database settings.'], ['Implemented SQL storage.']),
        ('Synthetic utility', ['Implemented a local text formatting utility.', 'Documented example utility commands.'],
         ['Implemented a text formatting utility.']),
    ]
    audit={'verified':True,'generation_id':'public-synthetic-generation','projects':[]}
    rankings=[]
    for name,base,library in portfolios:
        audit['projects'].append({'project':name,'base':[{'text':t} for t in base],
            'library':[{'text':t} for t in library],'final':[{'text':t} for t in base]})
        rankings.append({'title':name,'requirement_matches':[
            {'requirement_id':key,'requirement_text':text,'importance':'core',
             'match_label':'direct','coverage_points':5} for key,text in REQUIREMENTS.items()]})
    return deepcopy(audit),{'candidate_project_ranking':rankings}
