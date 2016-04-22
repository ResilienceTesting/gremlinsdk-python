# -*- mode: ruby -*-
# vi: set ft=ruby :

Vagrant.configure(2) do |config|
  config.vm.box = "ubuntu/trusty64"

  # Demo port for productpage
  config.vm.network "forwarded_port", guest: 9080, host: 9180
  config.vm.network "forwarded_port", guest: 9081, host: 9181
  config.vm.network "forwarded_port", guest: 9082, host: 9182
  config.vm.network "forwarded_port", guest: 9083, host: 9183

  # service proxy for gateway
  config.vm.network "forwarded_port", guest: 9877, host: 9877
  # service proxy for productpage
  config.vm.network "forwarded_port", guest: 9876, host: 9876
  # Elasticsearch
  config.vm.network "forwarded_port", guest: 29200, host: 29200

  # Create a private network, which allows host-only access to the machine
  # using a specific IP.
  config.vm.network "private_network", ip: "192.168.33.10/24"
  # config.vm.network "public_network"

  # config.vm.synced_folder ".", "/home/vagrant/gsdk"

  # Install docker
  config.vm.provision :docker

  # Install docker-compose
  config.vm.provision "shell", inline: <<-EOC
    test -e /usr/local/bin/docker-compose || \\
    curl -sSL https://github.com/docker/compose/releases/download/1.5.1/docker-compose-`uname -s`-`uname -m` \\
      | sudo tee /usr/local/bin/docker-compose > /dev/null
    sudo chmod +x /usr/local/bin/docker-compose
    test -e /etc/bash_completion.d/docker-compose || \\
    curl -sSL https://raw.githubusercontent.com/docker/compose/$(docker-compose --version | awk 'NR==1{print $NF}')/contrib/completion/bash/docker-compose \\
      | sudo tee /etc/bash_completion.d/docker-compose > /dev/null
    sudo apt-get install python-setuptools
  EOC

  config.vm.provider "virtualbox" do |vb|
     vb.memory = "3072"
     vb.cpus = 2
  end
end
