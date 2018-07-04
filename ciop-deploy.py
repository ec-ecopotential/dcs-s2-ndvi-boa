from git import Repo

import jenkins
import time
import lxml.etree as etree
import sys
import requests
import os
import string
import hashlib
import urllib2
import pytz
from datetime import datetime
import time
import owslib
from owslib.wps import monitorExecution
import uuid
from owslib.wps import WebProcessingService
import getpass 


def query_yes_no(question, default="yes"):
    """Ask a yes/no question via raw_input() and return their answer.

    "question" is a string that is presented to the user.
    "default" is the presumed answer if the user just hits <Enter>.
        It must be "yes" (the default), "no" or None (meaning
        an answer is required of the user).

    The "answer" return value is True for "yes" or False for "no".
    """
    valid = {"yes": True, "y": True, "ye": True,
             "no": False, "n": False}
    if default is None:
        prompt = " [y/n] "
    elif default == "yes":
        prompt = " [Y/n] "
    elif default == "no":
        prompt = " [y/N] "
    else:
        raise ValueError("invalid default answer: '%s'" % default)

    while True:
        sys.stdout.write(question + prompt)
        choice = raw_input().lower()
        if default is not None and choice == '':
            return valid[default]
        elif choice in valid:
            return valid[choice]
        else:
            sys.stdout.write("Please respond with 'yes' or 'no' "
                             "(or 'y' or 'n').\n")

class Pom:

    root = None
    tree = None
    pom_namespaces = { 'A':'http://maven.apache.org/POM/4.0.0' }
    
    def __init__(self):
        
        try:
            self.tree = etree.parse('pom.xml')
            self.root = self.tree.getroot()

        except IOError as e:
            print 'Error, run this utility as you would run maven'
            
    def get_version(self):
    
        el = self.root.xpath('/A:project/A:version', 
                             namespaces=self.pom_namespaces)
        
        return el[0].text
    
    def get_artifact_id(self):
    
        el = self.root.xpath('/A:project/A:artifactId', 
                             namespaces=self.pom_namespaces)
        
        return el[0].text
    
    def get_community(self):
    
        el = self.root.xpath('/A:project/A:properties/A:community', 
                             namespaces=self.pom_namespaces)
        
        return el[0].text

def submit_job(server, job, sleepSecs=3):
    
    last_build = server.get_job_info(job)['lastCompletedBuild']['number']
    
    server.build_job(job, {'RELEASE': 'true'})
    
    while server.get_job_info(job)['lastBuild']['number'] == last_build:
        
        time.sleep(sleepSecs)
        
    return server.get_job_info(job)['lastBuild']['number']


def monitor_build(server, job, sleepSecs=15):
    
    last_build_number = server.get_job_info(job)['lastBuild']['number']
    
    while server.get_build_info(job, last_build_number)['building']:
        
        time.sleep(sleepSecs)
    
    if str(server.get_build_info(job, last_build_number)['result']) == 'SUCCESS':
        
        return True
    
    if str(server.get_build_info(job, last_build_number)['result']) == 'FAILURE':
        
        return False
    
def main():
    
    pom = Pom()
    
    ows_context_url = 'https://store.terradue.com/api/%s/_applications/%s/%s/%s/%s-%s-context.xml' % (pom.get_community(), 
                                                                   pom.get_community(), 
                                                                   pom.get_artifact_id(),
                                                                   pom.get_version(), 
                                                                   pom.get_artifact_id(),
                                                                   pom.get_version())
    
    repo = Repo('./')
    assert not repo.bare

    git = repo.git

    git.config('user.email', 'fabrice.brito@terradue.com')
    git.config('user.name', 'fabricebrito')

    if query_yes_no('Merge master branch into docker branch?'):

        git.checkout('docker')

        try:
            git.merge('origin/master')
            git.commit(m='merge master into docker')
            git.push()
        
        except Exception as e:

            print(e)

    else: 
    
        sys.exit()

    if query_yes_no('Proceed with the build of the docker branch?'):    
       
        username = raw_input("Give me your Jenkins username? ")
        api_key = getpass.getpass('And your Jenkins API key:')

        api_key='ce9d038c8b4909aadf0da1ca16f352cc'
        
        server = jenkins.Jenkins(url='https://build.terradue.com',
                        username=username,
                        password=api_key)
    
        repositories = ['Gitlab Groups',
                'Github Organizations']

        job = 'communities/%s/%s/%s/docker' % (repositories[0], 
                                           pom.get_community(), 
                                           pom.get_artifact_id())
        
        for repository in repositories:
            
            try: 
        
                server.get_job_info(job)
    
            except jenkins.NotFoundException as e:
        
                pass
        
            else:
                break
                
            job = 'communities/%s/%s/%s/docker' % (repository, 
                                           pom.get_community(), 
                                           pom.get_artifact_id())
    
    
        print 'Build job %s' % job
        submit_job(server, job)
     
        print 'Monitoring build...'
        if monitor_build(server, job):
            
            print 'Job build completed'
         
        else:
            
            print 'Job build failed'
            sys.exit(1)
    
    if query_yes_no('Proceed with the application deployment on the production centre?'):            
    
        wps_url = 'https://%s-deployer.terradue.com/zoo-bin/zoo_loader.cgi' % pom.get_community()             
    
        wps = WebProcessingService(wps_url, verbose=False, skip_caps=False)
        
        process_id = 'DeployProcess'
        
        process = wps.describeprocess(process_id)
        
        inputs = [('applicationPackage', ows_context_url)]
        
        execution = owslib.wps.WPSExecution(url=wps.url)

        execution_request = execution.buildRequest(process_id, 
                                           inputs, 
                                           output = [('deployResult', False)])
        
        execution_response = execution.submitRequest(etree.tostring(execution_request))
        
        
        execution.parseResponse(execution_response)
        
        monitorExecution(execution)
        
        if execution.isSucceded(): 
            
            print 'Application deployed!'
            
        else: 
            print 'Application not deployed'
            sys.exit(1)
            
if __name__== '__main__':
    main()
