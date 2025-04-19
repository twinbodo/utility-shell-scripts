# utility-shell-scripts

To see the cron jobs for the current user: `crontab -l`
To edit the cron jobs for the current user: `crontab -e`

How to edit the keybindings?
1. you can navigate through the menu by selecting File (or Code on macOS) > Preferences > Keyboard Shortcuts.
2. Access Keybindings JSON:
    In the Keyboard Shortcuts editor, you’ll see an icon for opening keybindings.json in the top right corner.
3. Copy the file from the gitrepo and paste it there, Just done.

`displayplacer "id:1 enabled:true scaling:on origin:(0,0) degree:0" "id:2 enabled:true scaling:off origin:(-250,-1200) degree:0"`


Sample key keyboard manager object
`{
   "devices": [
       {
           "identifiers": {
               "is_keyboard": true,
               "product_id": 13330,
               "vendor_id": 14
           },
           "simple_modifications": [
               {
                   "from": { "key_code": "left_command" },
                   "to": [{ "key_code": "left_option" }]
               }
           ]
       },
       {
           "identifiers": {
               "is_keyboard": true,
               "product_id": 13330,
               "vendor_id": 14
           },
           "simple_modifications": [
               {
                   "from": { "key_code": "left_option" },
                   "to": [{ "key_code": "left_command" }]
               }
           ]
       }
   ],
   "name": "New profile custom",
   "selected": true,
   "virtual_hid_keyboard": { "keyboard_type_v2": "ansi" }
}

`