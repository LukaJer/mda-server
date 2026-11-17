import os
import shutil


def get_list_of_backups(folder_path):
    return [f for f in os.listdir(folder_path) if f.startswith("backup_") and f.endswith(".db")]


def choose_backup(backups):
    for i, backup in enumerate(backups):
        print(f"{i}: {backup}")

    while True:
        try:
            choice = int(input("Enter the number of the backup you want to load: "))
            if 0 <= choice < len(backups):
                return backups[choice]
            else:
                print("Invalid selection, please try again.")
        except ValueError:
            print("Please enter a valid number.")


def load_backup(folder_path, backup_name, db_name="measurements.db"):
    src_path = os.path.join(folder_path, backup_name)
    dst_path = os.path.join(folder_path, db_name)
    shutil.copy(src_path, dst_path)
    print(f"Backup '{backup_name}' has been loaded as '{db_name}'.")


def main():
    folder_path = os.path.dirname(os.path.realpath(__file__)) + "/../instance"
    backups = get_list_of_backups(folder_path)

    if not backups:
        print("No backups found.")
        return

    backup_name = choose_backup(backups)
    load_backup(folder_path, backup_name)


if __name__ == "__main__":
    main()
