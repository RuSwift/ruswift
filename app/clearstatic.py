import os
from argparse import ArgumentParser


parser = ArgumentParser()
parser.add_argument('path')


def is_sub(sub_: str, file_: str) -> bool:
    sub_name_, sub_ext_ = os.path.splitext(sub_)[0], os.path.splitext(sub_)[1]
    file_name_, file_ext_ = os.path.splitext(file_)[0], os.path.splitext(file_)[1]
    if str(sub_name_).startswith(file_name_) and sub_ext_ == file_ext_:
        if len(sub_name_) > len(file_name_):
            ch = sub_name_[len(file_name_)]
            if ch == '.':
                suffix_ = sub_name_[len(file_name_)+1:]
                suffix_part1_ = suffix_.split('.')[0]
                return len(suffix_part1_) == 12
            else:
                return False
        else:
            return False
    else:
        return False


if __name__ == '__main__':
    args = parser.parse_args()
    path = args.path
    if not os.path.isdir(path):
        raise RuntimeError(f'Path {path} does not exists')
    for root, directory, files in os.walk(path):
        counters = {}
        files_to_remove = [f for f in files if f.endswith('.gz')]
        clear_files = [f for f in files if f not in files_to_remove]
        #
        for file in clear_files:
            counters[file] = 0
            for sub in clear_files:
                if file != sub:
                    if is_sub(sub, file):
                        counters[file] += 1
        #
        file_keys = list(counters.keys())
        for file in file_keys:
            for sub in file_keys:
                if file != sub and file in counters and sub in counters:
                    if is_sub(sub, file):
                        if counters[file] > counters[sub]:
                            del counters[sub]
                            files_to_remove.append(sub)
        for file in files_to_remove:
            os.remove(os.path.join(root, file))
            print(f'file removed: {file}')