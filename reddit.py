import grequests, requests
import praw, psaw
from psaw import PushshiftAPI
import wx
import time 
import os 
import threading

class RedditApp: 

    standard_image_extension = "png"
    image_extensions = {"jpg", "png", "webm", "jpeg"}
    video_extensions = {"mp4", "gif"}

    gif_hosts = {"https://gyfcat.com/"}
    image_hosts = {"/pbs.twimg.com/", "/imgur.com/"}
    media_hosts = {"i.redd", "imgur", "gyfcat", "twimg"}

    subreddit = None 
    limit = None 
    scrape = 0 
    count = 0
    progress_bar_range = 0

    def __init__(self, client_id, client_secret, username, password, bot_name): 

        self.client_id = client_id
        self.client_secret = client_secret
        self.username = username
        self.password = password
        self.bot_name = bot_name
        self.reddit = praw.Reddit(client_id=self.client_id,
                                  client_secret=self.client_secret,
                                  user_agent=f"ChangeMeClient/0.1 by /u/{self.bot_name}",
                                  username=self.username,
                                  password=self.password)
        self.PS = psaw.PushshiftAPI()

        self.frame = wx.Frame(parent=None, title="Reddit", size=(325, 255))
        panel = wx.Panel(self.frame)

        subreddit_text = wx.StaticText(panel, label="Subreddit: ", pos=(20, 20))
        limit_text = wx.StaticText(panel, label="Limit: ", pos=(20, 50))
        directory_text = wx.StaticText(panel, label="Directory:", pos=(20, 80))
        self.download_text = wx.StaticText(panel, label="Waiting...", pos=(20, 140))
        self.progress_text = wx.StaticText(panel, label="0/0", pos=(20, 180))

        self.subreddit_textctrl = wx.TextCtrl(panel, pos=(100, 15))
        self.limit_textctrl = wx.TextCtrl(panel, pos=(100, 45))

        directory_button = wx.Button(panel, label="Select", pos=(100, 75))
        directory_button.Bind(wx.EVT_BUTTON, self._set_directory)
        scrape_button  = wx.Button(panel, label="Scrape", pos=(100, 105))
        scrape_button.Bind(wx.EVT_BUTTON, self._start_scrape)

        self.progress_bar = wx.Gauge(panel, range=100, pos=(20, 160), size=(265, 15))
        self.directory = os.getcwd()

        self.scrape_thread = threading.Thread(target=self._scrape, daemon=True)

        self.frame.Show()

    def _download_media(self, urls, update_progress=True):
        # self._check_directory()
        urls = self._check_duplicates(urls)
        responses = self._get_responses(urls)
        self._download(responses)
        self._reset()
        self._message_box("Download completed")
        return 1

    def _get_submissions(self, subreddit_name, limit):
        submissions = set()
        for submission in self.reddit.subreddit(subreddit_name).stream.submissions():
            submissions.add(submission)
            if len(submissions) == limit: 
                return submissions 

    def _psaw_get_media(self, filter, subreddit="pics", limit=0, after=0):
        submissions = self._psaw_search_submissions("url", subreddit, limit)
        return [s.url for s in submissions if any(e in s.url for e in self.media_hosts)]

    def _fix_media_urls(self, urls):
        found = 0
        for i in range(len(urls)):
            current_e = urls[i]
            if any(h in current_e for h in self.image_hosts):
                for ext in self.image_extensions: 
                    if ext in current_e:
                        urls[i] = current_e[:current_e.index(ext) + len(ext)]
                        found = 1
                        break
                if not found:
                    urls[i] = current_e + ".png"
                else: 
                    found = 0
                continue 
            if any(h in current_e for h in self.gif_hosts):
                if current_e[-3:] not in self.gif_hosts:
                    urls[i] = current_e + ".gif"
        return urls

    def _check_duplicates(self, urls):
        return [url for url in urls if not os.path.exists(f"{self.directory}\\{url}")]
    
    def _get_media(self, filter, subreddit_name, limit): 
        urls = self._psaw_get_media(filter, subreddit=subreddit_name, limit=limit)
        return self._fix_media_urls(urls)

    def _download(self, responses, update_progress=True):
        for r in responses:
            media_name = r.url.split('/')[-1]
            path = f"{self.directory}\\{media_name}"
            if not os.path.isfile(path):
                with open(path, "wb") as f:
                    for chunk in r:
                        f.write(chunk)
            if update_progress:
                self._update_progress(r.url)
        return 1

    def _check_directory(self):
        if not os.path.exists(self.directory):
            os.mkdir(self.directory)

    def _get_responses(self, urls): 
        requests = (grequests.get(u) for u in urls)
        return grequests.imap(requests)

    def _psaw_search_submissions(self, filter, subreddit="pics", limit=0, after=0):
        return self.PS.search_submissions(filter=filter, subreddit=subreddit, limit=limit, after=after)

    def _set_directory(self, event): 
        directory_dialog = wx.DirDialog(self.frame, "Choose a directory:", defaultPath=self.directory)
        if directory_dialog.ShowModal() == wx.ID_OK: 
            self.directory = directory_dialog.GetPath()

    def _update_progress(self, media_name): 
        self.download_text.SetLabel(f"Downloading: {media_name}")
        self.progress_text.SetLabel(f"{self.count}/{self.progress_bar_range}")
        self.count += 1
        self.progress_bar.SetValue(self.count)

    def _set_progress_range(self, progress_range):
        self.progress_bar_range = progress_range
        self.progress_bar.SetRange(progress_range)

    def _start_scrape(self, event): 
        self.subreddit = self.subreddit_textctrl.GetValue()
        self.limit = self.limit_textctrl.GetValue()
        if self.subreddit and self.limit: 
            self.limit = int(self.limit)
            self.scrape_thread.start()
        else: 
            self._message_box("Subreddit or Limit missing")

    def _message_box(self, message):
        wx.MessageBox(message, "Info", wx.OK)

    def _reset(self): 
        self.subreddit = None 
        self.subreddit_textctrl.SetValue("")
        self.limit = None 
        self.limit_textctrl.SetValue("")
        self.scrape = 0 
        self.progress_bar_range = 0
        self.progress_bar.SetValue(0)
        self.download_text.SetLabel("Waiting...")
        self.progress_text.SetLabel("0/0")
    
    def _scrape(self): 
        urls = self._get_media("url", self.subreddit, self.limit)
        self._set_progress_range(len(urls))
        self._download_media(urls) 

    def __get_media(self, subreddit_name, limit, extensions):
        media = set()
        for submission in self.reddit.subreddit(subreddit_name).stream.submissions():
            url = submission.url
            if not any(e in url for e in self.media_hosts):
                if any(ext in url for ext in extensions):
                    media.add(url)
                    if len(media) == limit:
                        return media

if __name__ == "__main__":
    app = wx.App()
    RedditApp("")
    app.MainLoop() 
