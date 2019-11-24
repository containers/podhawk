from json import loads
from subprocess import run
from typing import List

ctn_list: List[tuple] = []
img_id_name_tag: List[tuple] = []
img_updated: List[str] = []


def update_img(data):
    """update image using podman pull and if updated append it to
    global var to recreate containers

    Args:
        data (list): image id, name and tag
    """
    img: tuple
    for img in data:
        img_name: str = img[1]
        old_id: str = img[0]
        pull_output: str = run(
            ['podman', 'pull', '-q', img_name],
            capture_output=True).stdout.decode('utf-8').rstrip()
        if pull_output != old_id:
            img_updated.append(img_name)


def identify_img_name_tag(data):
    """extract image name with tag from podman images (json) and
    append it to global var for later use

    Args:
        data (list): json from podman images
    """
    for image in data:
        if image['names'] is not None:
            img_id_name_tag.append((str(image['id']), image['names'][0]))


def prepare_containers_list(data):
    """prepare global var used to recreate running container when
    image's updated

    Args:
        data (list): json from podman ps
    """
    for container in data:
        if 'Up' in container['Status']:
            ctn_list.append((str(container['ID']), container['Image']))


# get current containers
ps_output = run(['podman', 'ps', '--format', 'json'],
                capture_output=True).stdout.decode('utf-8')
prepare_containers_list(loads(ps_output))

# get current images
images_output = run(['podman', 'images', '--format', 'json'],
                    capture_output=True).stdout.decode('utf-8')
identify_img_name_tag(loads(images_output))

# pull images
update_img(img_id_name_tag)
