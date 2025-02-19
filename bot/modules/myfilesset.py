from asyncio.subprocess import PIPE, create_subprocess_exec as exec
from json import loads as jsonloads
from asyncio import sleep, TimeoutError
from os.path import splitext
from bot.helper.ext_utils.message_utils import editMarkup, editMessage, sendMarkup, sendMessage
from bot.helper.ext_utils.misc_utils import ButtonMaker, get_readable_size
from pyrogram import filters

from bot.helper.ext_utils.rclone_utils import get_rclone_config

async def myfiles_settings(message, drive_name, drive_base, edit=False, is_folder=False):
     if message.reply_to_message:
        user_id= message.reply_to_message.from_user.id
     else:
        user_id= message.from_user.id
     
     buttons= ButtonMaker()

     if len(drive_base) == 0:
          buttons.cb_buildbutton("📁 Calculate folder size", f"myfilesmenu^size^{user_id}")
          buttons.cb_buildbutton("📁 Create empty directory", f"myfilesmenu^mkdir^{user_id}")
          buttons.cb_buildbutton("🗑 Delete empty directories", f"myfilesmenu^rmdir^{user_id}")
          buttons.cb_buildbutton("🗑 Delete duplicate files", f"myfilesmenu^dedupe^{user_id}")   
     else:
          if is_folder:
               buttons.cb_buildbutton(f"📁 Calculate folder size", f"myfilesmenu^size^{user_id}")
               buttons.cb_buildbutton("🗑 Delete duplicate files", f"myfilesmenu^dedupe^{user_id}")      
               buttons.cb_buildbutton(f"🗑 Delete folder", f"myfilesmenu^delete^folder^{user_id}")
               buttons.cb_buildbutton("📁 Create empty directory", f"myfilesmenu^mkdir^{user_id}")                       
               buttons.cb_buildbutton("🗑 Delete empty directories", f"myfilesmenu^rmdir^{user_id}")                         
          else:
               buttons.cb_buildbutton("📝 Rename", f"myfilesmenu^rename^file^{user_id}")
               buttons.cb_buildbutton("🗑 Delete", f"myfilesmenu^delete^file^{user_id}")
     
     buttons.cb_buildbutton("⬅️ Back", f"myfilesmenu^back_remotes_menu^{user_id}", 'footer')
     buttons.cb_buildbutton("✘ Close Menu", f"myfilesmenu^close^{user_id}", 'footer')
     
     msg= f"<b>Path:</b><code>{drive_name}:{drive_base}</code>"

     if edit:
          await editMessage(msg, message, reply_markup= buttons.build_menu(2))
     else:
          await sendMarkup(msg, message, reply_markup= buttons.build_menu(2))

async def calculate_size(message, drive_base, drive_name, user_id):
     buttons= ButtonMaker()
     path = get_rclone_config(user_id)
     data = await rclone_size(message, drive_base, drive_name, path)
     if data is not None:
          total_size = get_readable_size(data[1])
          msg= f"Total Files: {data[0]}\nFolder Size: {total_size}"
          buttons.cb_buildbutton("⬅️ Back", f"myfilesmenu^back_remotes_menu^{user_id}", 'footer')
          buttons.cb_buildbutton("✘ Close Menu", f"myfilesmenu^close^{user_id}", 'footer')
          await editMessage(msg, message, reply_markup= buttons.build_menu(1))

async def search_action(client, message, query, drive_name, user_id):
     conf_path = get_rclone_config(user_id)
     question= await sendMessage("Send file name to search, /ignore to cancel", message)
     try:
          response = await client.listen.Message(filters.text, id=filters.user(user_id), timeout=60)
     except TimeoutError:
          await sendMessage("Too late 60s gone, try again!", message)
     else:
          if response:
               text= response.text
               try:
                    if "/ignore" in text:
                         await query.answer("Okay cancelled!")
                         await client.listen.Cancel(filters.user(user_id))
                    else:
                         search_msg= await sendMessage("**⏳Searching file on remote...**\n\nPlease wait, it may take some time", question)
                         conf_path = get_rclone_config(user_id)
                         cmd = ["rclone", "lsjson", "--files-only", "-R", f'--config={conf_path}', "--include", f"*{text}*", f"{drive_name}:"] 
                         process = await exec(*cmd, stdout=PIPE, stderr=PIPE)
                         out, err = await process.communicate()
                         out = out.decode().strip()
                         return_code = await process.wait()
                         if return_code != 0:
                              err = err.decode().strip()
                              await sendMessage(f'Error: {err}', message)
                              return
                         if len(out) > 0:
                              data= jsonloads(out)
                              msg= f"<b>Found {len(data)} files:\n\n</b>"
                              for index, file in enumerate(data, start=1):
                                   name= file['Name']
                                   path= file['Path']
                                   cmd = ["rclone", "link", f'--config={conf_path}', f"{drive_name}:{path}"]
                                   process = await exec(*cmd, stdout=PIPE, stderr=PIPE)
                                   out, err = await process.communicate()
                                   link = out.decode().strip()
                                   return_code = await process.wait()
                                   if return_code == 0:
                                        msg += f"{index}. <a href='{link}'>{name}</a>\n"
                                   else:
                                        msg += f"{index}. <code>{name}</code>\n"
                                   await sleep(0.5)
                              await search_msg.delete()
                              await sendMessage(msg, message)
                         else:
                              await sendMessage("No file found", message)
               except Exception as ex:
                    await sendMessage(str(ex), message) 
     finally:
          await question.delete()

async def delete_selection(message, user_id, is_folder=False):
     buttons= ButtonMaker()
     msg= ""
     if is_folder:
          buttons.cb_buildbutton("Yes", f"myfilesmenu^yes^folder^{user_id}")
          buttons.cb_buildbutton( "No", f"myfilesmenu^no^folder^{user_id}")
          msg += f"Are you sure you want to delete this folder permanently?"
     else:
          buttons.cb_buildbutton("Yes", f"myfilesmenu^yes^file^{user_id}")
          buttons.cb_buildbutton("No", f"myfilesmenu^no^file^{user_id}")
          msg += f"Are you sure you want to delete this file permanently?"
     await editMessage(msg, message, reply_markup= buttons.build_menu(2))

async def delete_selected(message, user_id, drive_base, drive_name, is_folder=False):   
     buttons= ButtonMaker()
     msg= ""
     conf_path = get_rclone_config(user_id)
     if is_folder:
          await rclone_purge(message, drive_base, drive_name, conf_path)    
          msg += f"The folder has been deleted successfully!!"
     else:
          await rclone_delete(message, drive_base, drive_name, conf_path)  
          msg += f"The file has been deleted successfully!!"
     buttons.cb_buildbutton("⬅️ Back", f"myfilesmenu^back_remotes_menu^{user_id}", 'footer')
     buttons.cb_buildbutton("✘ Close Menu", f"myfilesmenu^close^{user_id}", 'footer')
     await editMessage(msg, message, reply_markup= buttons.build_menu(1))

async def delete_empty_dir(message, user_id, rclone_drive, base_dir):
     buttons= ButtonMaker()
     conf_path = get_rclone_config(user_id)
     await rclone_rmdirs(message, rclone_drive, base_dir, conf_path)
     buttons.cb_buildbutton("⬅️ Back", f"myfilesmenu^back_remotes_menu^{user_id}", 'footer')
     buttons.cb_buildbutton("✘ Close Menu", f"myfilesmenu^close^{user_id}", 'footer')
     msg = "Directories successfully deleted!!"
     await editMessage(msg, message, reply_markup= buttons.build_menu(1))

async def rclone_size(message, drive_base, drive_name, conf_path):
     await editMessage("**⏳Calculating Folder Size...**\n\nPlease wait, it will take some time depending on number of files", message)
     cmd = ["rclone", "size", f'--config={conf_path}', f"{drive_name}:{drive_base}", "--json"] 
     process = await exec(*cmd, stdout=PIPE, stderr=PIPE)
     stdout, stderr = await process.communicate()
     stdout = stdout.decode().strip()
     return_code = await process.wait()
     if return_code != 0:
          err = stderr.decode().strip()
          await sendMessage(f'Error: {err}', message)
          return
     data = jsonloads(stdout)
     files = data["count"]
     size = data["bytes"]
     return (files, size)

async def rclone_purge(message,drive_base, drive_name, conf_path):
     cmd = ["rclone", "purge", f'--config={conf_path}', f"{drive_name}:{drive_base}"] 
     process = await exec(*cmd, stdout=PIPE, stderr=PIPE)
     stdout, stderr = await process.communicate()
     stdout = stdout.decode().strip()
     return_code = await process.wait()
     if return_code != 0:
          err = stderr.decode().strip()
          return await sendMessage(f'Error: {err}', message)

async def rclone_delete(message, drive_base, drive_name, conf_path):
     cmd = ["rclone", "delete", f'--config={conf_path}', f"{drive_name}:{drive_base}"] 
     process = await exec(*cmd, stdout=PIPE, stderr=PIPE)
     stdout, stderr = await process.communicate()
     stdout = stdout.decode().strip()
     return_code = await process.wait()
     if return_code != 0:
          err = stderr.decode().strip()
          return await sendMessage(f'Error: {err}', message)

async def rclone_rmdirs(message, drive_name, drive_base, conf_path):
     await editMessage("**⏳Removing empty directories...**\n\nPlease wait, it may take some time depending on number of dirs", message)
     cmd = ["rclone", "rmdirs", f'--config={conf_path}', f"{drive_name}:{drive_base}"] 
     process = await exec(*cmd, stdout=PIPE, stderr=PIPE)
     stdout, stderr = await process.communicate()
     stdout = stdout.decode().strip()
     return_code = await process.wait()
     if return_code != 0:
          err = stderr.decode().strip()
          return await sendMessage(f'Error: {err}', message)

async def rclone_mkdir(client, message, drive_name, base_dir, tag):
     user_id= message.reply_to_message.from_user.id
     conf_path = get_rclone_config(user_id)
     question= await sendMessage("Send name for directory, /ignore to cancel", message)
     try:
          response = await client.listen.Message(filters.text, id=filters.user(user_id), timeout= 30)
     except TimeoutError:
          await sendMessage("Too late 30s gone, try again!", message)
     else:
          if response:
               try:
                    if "/ignore" in response.text:
                         await client.listen.Cancel(filters.user(user_id))
                    else:
                         edit_mgs= await sendMessage("⏳Creating Directory...", message)
                         path= f'{base_dir}/{response.text}'
                         cmd = ["rclone", "mkdir", f'--config={conf_path}', f"{drive_name}:{path}"] 
                         process = await exec(*cmd, stdout=PIPE, stderr=PIPE)
                         stdout, stderr = await process.communicate()
                         stdout = stdout.decode().strip()
                         return_code = await process.wait()
                         if return_code != 0:
                              err = stderr.decode().strip()
                              return await sendMessage(f'Error: {err}', message)
                         msg = "<b>Directory created successfully.\n\n</b>" 
                         msg += f"<b>Path: </b><code>{drive_name}:{path}</code>\n\n"
                         msg += f'<b>cc:</b> {tag}\n\n' 
                         await editMessage(msg, edit_mgs)
               except Exception as ex:
                    await sendMessage(str(ex), message) 
     finally:
          await question.delete()

async def rclone_dedupe(message, rclone_drive, drive_base, user_id, tag):
     msg= "**⏳Deleting duplicate files**\n"
     msg += "\nIt may take some time depending on number of duplicates files"
     edit_msg= await editMessage(msg, message)
     conf_path = get_rclone_config(user_id)
     cmd = ["rclone", "dedupe", "newest", "--tpslimit", "4", "--transfers", "1", "--fast-list", f'--config={conf_path}', f"{rclone_drive}:{drive_base}"] 
     process = await exec(*cmd, stdout=PIPE, stderr=PIPE)
     stdout, stderr = await process.communicate()
     stdout = stdout.decode().strip()
     return_code = await process.wait()
     if return_code != 0:
          err = stderr.decode().strip()
          return await sendMessage(f'Error: {err}', message)
     msg= "<b>Dedupe completed successfully ✅</b>\n"
     msg += f'<b>cc:</b> {tag}\n'
     button= ButtonMaker()
     button.cb_buildbutton("⬅️ Back", f"myfilesmenu^back_remotes_menu^{user_id}", 'footer')
     await editMarkup(msg, edit_msg, reply_markup=button.build_menu(1))

async def rclone_rename(client, message, rclone_drive, drive_base, tag):
     user_id= message.reply_to_message.from_user.id
     conf_path = get_rclone_config(user_id)
     question= await sendMessage("Send new name for file, /ignore to cancel", message)
     try:
          response = await client.listen.Message(filters.text, id=filters.user(user_id), timeout= 30)
     except TimeoutError:
          await sendMessage("Too late 30s gone, try again!", message)
     else:
          if response:
               try:
                    if "/ignore" in response.text:
                         await question.reply("Okay cancelled!")
                         await client.listen.Cancel(filters.user(user_id))
                    else:
                         new_name= response.text
                         edit_msg= await sendMessage("⏳Renaming file...", message) 
                         list_base= drive_base.split("/")
                         if len(list_base) > 1:
                              dest = list_base[:-1]
                              dest = "/".join(dest)
                              file = list_base[-1]
                              _, ext= splitext(file)
                              path = f'{dest}/{new_name}{ext}'
                         else:
                              file = list_base[0]
                              _, ext= splitext(file)
                              path = f'{new_name}{ext}'
                         cmd = ["rclone", "moveto", f'--config={conf_path}', f"{rclone_drive}:{drive_base}", f"{rclone_drive}:{path}"]
                         process = await exec(*cmd, stdout=PIPE, stderr=PIPE)
                         stdout, stderr = await process.communicate()
                         stdout = stdout.decode().strip()
                         return_code = await process.wait()
                         if return_code != 0:
                              err = stderr.decode().strip()
                              return await sendMessage(f'Error: {err}', message)
                         msg= "<b>File renamed successfully.</b>\n\n"
                         msg += f"<b>Old path: </b><code>{rclone_drive}:{drive_base}</code>\n\n"
                         msg += f"<b>New path: </b><code>{rclone_drive}:{path}</code>\n\n"
                         msg += f'<b>cc: {tag}</b>'     
                         await editMessage(msg, edit_msg)
               except Exception as ex:
                    await sendMessage(str(ex), message) 
     finally:
          await question.delete()





     

     

