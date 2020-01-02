from json import loads
from subprocess import run, PIPE, STDOUT
from typing import List


def remove_old_container(old_ctn_id):
    print(f'Removing old container {old_ctn_id}')
    remove = run(['podman', 'rm', old_ctn_id],
                 capture_output=True).stdout.decode('utf-8')
    print(f'Removing … {remove}')


def post_healthcheck(old_ctn_id, new_ctn_id, status):
    if 'NA' in status:
        print('No healthcheck defined in this image… '
              'We continue at your own risk')
        remove_old_container(old_ctn_id)
    elif 'true' in status:
        print('Healthcheck success')
        remove_old_container(old_ctn_id)
    else:
        print(f'Healthcheck failed, restarting old container {old_ctn_id}')
        print("New container forced to stop and not removed "
              "to permit you to analyze logs")
        run(['podman', 'stop', new_ctn_id])
        start_old = run(['podman', 'start', old_ctn_id],
                        capture_output=True).stdout.decode('utf-8')
        print(f'Starting … {start_old}')


def health_check(container_id):
    """
    Analyze healthcheck status (3 times) and return the value
    needed by post_healthcheck
    Args:
        container_id (str): new container id

    Returns:
        A string that permit to know in which situation we are
    """
    status: str = 'false'
    for i in range(3):
        output = run(['podman', 'healthcheck', 'run', container_id],
                     stdout=PIPE, stderr=STDOUT).stdout.decode('utf-8')
        print(f'healthcheck {i}/3: {output}')
        if 'has no defined healthcheck' in output:
            return 'NA'
        elif 'unhealthy' in output:
            status = 'false'
        else:
            status = 'true'
    return status


def recreate_container(containers_data):
    """
    execute commands included in data to recreate containers

    Args:
        containers_data (list): informations to recreate containers

    Returns:
        Print status about each step for each container
    """
    for element in containers_data:
        old_ctn_id: str = element[0]
        new_ctn_cli: str = element[1]

        print(f'Recreating container id : {old_ctn_id}')
        print(f'Stopping {old_ctn_id}')
        stop_old = run(['podman', 'stop', old_ctn_id],
                       capture_output=True).stdout.decode('utf-8')
        print(f'Stopping … {stop_old}')

        print(f'Starting new container …')
        start_new = run(new_ctn_cli,
                        capture_output=True).stdout.decode('utf-8')
        print(f'Starting … {start_new}')

        healthcheck_status: str = health_check(start_new)
        post_healthcheck(old_ctn_id, start_new, healthcheck_status)

    print('Jobs done')


def format_envs_cli(envs_data):
    """
    return command line for environment variables

    Args:
        envs_data (list): from inspect_container

    Returns:
        The command line needed otherwise blank line
    """
    added_automatically = ('PATH=', 'TERM=', 'HOSTNAME=', 'container=',
                           'GODEBUG=', 'XDG_CACHE_HOME=', 'HOME=')

    if len(envs_data) > 0:
        envs = envs_data
        for prefix in added_automatically:
            envs_to_remove = [env for env in envs if prefix in env]
        for env in envs_to_remove:
            envs.remove(env)
        return '{0},'.format(','.join([f'-e,"{env}"' for env in envs]))
    else:
        return ''


def format_network_ports_cli(network_data):
    """
    return command line for network ports

    Args:
        network_data (list): from inspect_container

    Returns:
        The command line needed otherwise blank line
    """
    network_ports_pre_cli: List[str] = []
    if len(network_data) > 0:
        for port in network_data:
            host_port = port['hostPort']
            container_port = port['containerPort']
            host_ip = port['hostIP']
            network_ports_pre_cli.append(
                f'-p,{host_ip}:{host_port}:{container_port}'
            ) if len(host_ip) > 0 else network_ports_pre_cli.append(
                f'-p,{host_port}:{container_port}')
        return '{0},'.format(', '.join(network_ports_pre_cli))
    else:
        return ''


def format_mounts_cli(mounts_data):
    """
    return command line for mounts

    Args:
        mounts_data (list): from inspect_container

    Returns:
        The command line needed otherwise blank line
    """
    mounts_pre_cli: List[tuple] = []
    if len(mounts_data) > 0:
        for mount in mounts_data:
            source = mount['Source']
            destination = mount['Destination']
            mounts_pre_cli.append(f'-v,{source}:{destination}')
        return '{0},'.format(', '.join(mounts_pre_cli))
    else:
        return ''


def format_restart_cli(restart_data):
    """
    return command line for restart policy

    Args:
        restart_data (list): from inspect_container

    Returns:
        The command line needed otherwise blank line
    """
    if len(restart_data['Name']) > 0:
        restart_policy_name = restart_data['Name']
        return f'--restart={restart_policy_name}'
    else:
        return ''


def inspect_container(containers_list):
    """
    inspect each container and rebuild CLI to recreate each container

    Args:
        containers_list (list): list of running containers

    Returns:
        List of cli needed to recreate each container
    """
    ctn_to_recreate: List[tuple] = []

    for ctn in containers_list:
        ctn_id = ctn[0]
        print(f'    - {ctn_id} in progress')
        ctn_image = ctn[1]
        inspect_output = run(['podman', 'inspect', '--format', 'json', ctn_id],
                             capture_output=True).stdout.decode('utf-8')
        inspect_json = loads(inspect_output)[0]
        mounts = inspect_json['Mounts']
        network_ports = inspect_json['NetworkSettings']['Ports']
        envs = inspect_json['Config']['Env']
        restart_policy = inspect_json['HostConfig']['RestartPolicy']
        cli_restart_policy = format_restart_cli(restart_policy)
        cli_mounts = format_mounts_cli(mounts)
        cli_network_ports = format_network_ports_cli(network_ports)
        cli_envs = format_envs_cli(envs)
        cli = f'podman, run, -d, {cli_mounts}{cli_envs}{cli_network_ports}' \
              f'{cli_restart_policy} {ctn_image}'.split(sep=',')
        ctn_to_recreate.append((ctn_id, cli))
    return ctn_to_recreate


def containers_to_recreate(containers_list, images_updated):
    """return which containers are to recreate

    Args:
        containers_list (list): list running containers
        images_updated: (list) updated images

    Returns:
        List of containers needed to be recreated
    """
    result: List[tuple] = []

    for container in containers_list:
        if container[1] in images_updated:
            result.append(container)

    return result


def update_img(data):
    """update image using podman pull and if updated append it to
    global var to recreate containers

    Args:
        data (list): image id, name and tag
    Returns:
        List of images updated
    """
    updated: List = []
    img: tuple

    for img in data:
        img_name: str = img[1]
        old_id: str = img[0]
        print(f'    - {img_name}')
        pull_output: str = run(
            ['podman', 'pull', '-q', img_name],
            capture_output=True).stdout.decode('utf-8').rstrip()
        if pull_output != old_id:
            updated.append(img_name)
    return updated


def identify_img_name_tag(data):
    """extract image name with tag from podman images (json) and
    append it to global var for later use

    Args:
        data (list): json from podman images
    """
    extracted: List[tuple] = []

    for image in data:
        if image['names'] is not None:
            extracted.append((str(image['id']), image['names'][0]))
    return extracted


def prepare_containers_list(data):
    """prepare global var used to recreate running container when
    image's updated

    Args:
        data (list): json from podman ps
    """
    running_list: List[tuple] = []

    for container in data:
        if 'Up' in container['Status']:
            running_list.append((str(container['ID']), container['Image']))
    return running_list


def main():
    """
    Executed only when run as a script
    """
    print('Gathering information about running containers')
    ps_output = run(['podman', 'ps', '--format', 'json'],
                    capture_output=True).stdout.decode('utf-8')
    ctn_list: List[tuple] = prepare_containers_list(loads(ps_output))

    print('Gathering information about images')
    images_output = run(['podman', 'images', '--format', 'json'],
                        capture_output=True).stdout.decode('utf-8')
    img_id_name_tag: List[tuple] = identify_img_name_tag(loads(images_output))

    print('Updating images:')
    img_updated: List[str] = update_img(img_id_name_tag)

    if (len(img_updated) > 0) & (len(ctn_list) > 0):
        to_recreate: List[tuple] = containers_to_recreate(
            ctn_list, img_updated)
        if len(to_recreate) > 0:
            print('Inspecting running containers:')
            to_recreate_cli: List[tuple] = inspect_container(to_recreate)
            recreate_container(to_recreate_cli)
        else:
            print("No needed to recreate containers")
    else:
        print('No container to recreate')


if __name__ == "__main__":
    main()
