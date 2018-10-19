#!/usr/bin/env python3

import platform
import re
import json
import os
import sys
import glob
from github import Github

maintainer = 'emiliano.heyns@iris-advies.com'
architectures = ['i386', 'amd64']
gpg = 'dpkg'

if sys.version_info[0] >= 3:
  from urllib.request import urlopen
  from html.parser import HTMLParser
  from urllib.request import urlretrieve
  from http.client import HTTPSConnection
else:
  from urllib2 import urlopen
  from HTMLParser import HTMLParser
  from urllib import urlretrieve
  from httplib import HTTPSConnection

def run(cmd):
  print("\n" + cmd)
  os.system(cmd)

def write(filename, lines):
  print(f"\n# writing {filename}\n")

  with open(filename, 'w') as f:
    for line in lines:
      f.write(line + "\n")

class Repo:
  def __init__(self):
    self.repo = 'repo'

  def publish(self):
    run(f'mkdir -p {self.repo}')
    run(f'gpg --armor --export {gpg} > {self.repo}/deb.gpg.key')
    run(f'cd {self.repo} && apt-ftparchive packages . > Packages')
    run(f'bzip2 -kf {self.repo}/Packages')
    run(f'cd {self.repo} && apt-ftparchive release . > Release')
    run(f'gpg --yes -abs -u {gpg} -o {self.repo}/Release.gpg {self.repo}/Release')

    write(f'{self.repo}/install.sh', [
      'curl --silent -L https://github.com/retorquere/zotero_deb/releases/download/apt-get/deb.gpg.key | sudo apt-key add -',
      '',
      'cat << EOF | sudo tee /etc/apt/sources.list.d/zotero.list',
      'deb https://github.com/retorquere/zotero_deb/releases/download/apt-get/ ./',
      'EOF'
    ])

    description = """
    One-time installation of the repo: 
    'curl --silent -L https://sourceforge.net/projects/zotero-deb/files/install.sh | sudo bash'. 
    after this you can install and update in the usual way: 
    'sudo apt-get update; sudo apt-get install zotero jurism'
    """.replace("\n", ' ')

    run(f'github-release release --user retorquere --repo zotero_deb --tag apt-get --name "Debian packages for Zotero/Juris-M" --description "{description}"')
    for f in os.listdir(self.repo):
      run(f'cd {self.repo} && github-release upload --user retorquere --repo zotero_deb --tag apt-get --name {f} --file {f} --replace')

class Package:
  def __init__(self, client, name, repo):
    self.machine = {'amd64': 'x86_64', 'i386': 'i686'}
    self.client = client
    self.name = name
    self.repo = repo

  def deb(self, arch):
    return f'{self.repo}/{"_".join([self.client, self.version, arch])}.deb'

  def build(self, arch):
    print()

    deb = self.deb(arch)

    if os.path.exists(deb):
      print(f"# not rebuilding {deb}\n")
      return

    print(f"# Building {deb}\n")

    run(f'mkdir -p {self.repo}')

    run(f'rm -rf build client.tar.bz2 {deb}')
    run(f'mkdir -p build/usr/lib/{self.client} build/usr/share/applications build/DEBIAN')
    run(f'curl -L -o client.tar.bz2 "{self.url(arch)}"')
    run(f'tar --strip 1 -xpf client.tar.bz2 -C build/usr/lib/{self.client}')

    write(f'build/usr/share/applications/{self.client}.desktop', [
      '[Desktop Entry]',
      'Name=Zotero',
      f'Name={self.name}',
      'Comment=Open-source reference manager',
      f'Exec=/usr/lib/{self.client}/{self.client}',
      f'Icon=/usr/lib/{self.client}/chrome/icons/default/default48.png',
      'Type=Application',
      'StartupNotify=true',
    ])

    write('build/DEBIAN/control', [
      f'Package: {self.client}',
      f'Architecture: {arch}',
      f'Maintainer: {maintainer}',
      'Section: Science',
      'Priority: optional',
      f'Version: {self.version}',
      f'Description: {self.name} is a free, easy-to-use tool to help you collect, organize, cite, and share research',
    ])

    run(f'dpkg-deb --build -Zgzip build {deb}')
    run(f'dpkg-sig -k {gpg} --sign builder {deb}')

class Zotero(Package):
  def __init__(self, repo):
    super().__init__('zotero', 'Zotero', repo) 

    response = urlopen('https://www.zotero.org/download/').read()
    if type(response) is bytes: response = response.decode("utf-8")
    for line in response.split('\n'):
      if not '"standaloneVersions"' in line: continue
      line = re.sub(r'.*Downloads,', '', line)
      line = re.sub(r'\),', '', line)
      versions = json.loads(line)
      self.version = versions['standaloneVersions'][f'linux-{platform.machine()}']
      break

  def url(self, arch):
    return f'https://www.zotero.org/download/client/dl?channel=release&platform=linux-{self.machine[arch]}&version={self.version}'

class JurisM(Package):
  def __init__(self, repo):
    super().__init__('jurism', 'Juris-M', repo) 

    release = HTTPSConnection('our.law.nagoya-u.ac.jp')
    release.request('GET', f'/jurism/dl?channel=release&platform=linux-{platform.machine()}')
    release = release.getresponse()
    release = release.getheader('Location')
    self.version = release.split('/')[-2]

  def url(self, arch):
    return f'https://github.com/Juris-M/assets/releases/download/client%2Frelease%2F{self.version}/Jurism-{self.version}_linux-{self.machine[arch]}.tar.bz2'

print("\n# creating repo")
repo = Repo()

zotero = Zotero(repo.repo)
jurism = JurisM(repo.repo)
for arch in architectures:
  zotero.build(arch)
  jurism.build(arch)

print("\n# publishing repo")
repo.publish()
