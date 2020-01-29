import sys
import os
import threading
import urllib

import requests
import hashlib
import re
import time
from PyQt5.QtGui import QBrush, QColor

if hasattr(sys, 'frozen'):
    os.environ['PATH'] = sys._MEIPASS + ";" + os.environ['PATH']
from PyQt5 import QtCore
from PyQt5.QtCore import QCoreApplication, QFile, QTextStream, QObject, pyqtSignal, QThread
from PyQt5.QtWidgets import QApplication, QDialog, QTableWidgetItem, QMainWindow, QPushButton, QProgressBar
from ui_dilidili import Ui_MainWindow

# For QThread Use.
class CidParser(QObject):
    sigPercentage = pyqtSignal(int)
    sigTitleList = pyqtSignal(list)
    sigThreadPool = pyqtSignal(dict)
    sigDownPercentage = pyqtSignal(str, int)
    def __init__(self):
        super(QObject, self).__init__()
        self.start_url = ""
        self.threadpool = {}

    def setUrl(self, url):
        self.start_url = url

    def download(self,cid):
        self.threadpool[cid][0].start()

    def get_play_list(self, start_url, cid, quality):
        entropy = 'rbMCKn@KuamXWlPMoJGsKcbiJKUfkPF_8dABscJntvqhRSETg'
        appkey, sec = ''.join([chr(ord(i) + 2) for i in entropy[::-1]]).split(':')
        params = 'appkey=%s&cid=%s&otype=json&qn=%s&quality=%s&type=' % (appkey, cid, quality, quality)
        chksum = hashlib.md5(bytes(params + sec, 'utf8')).hexdigest()
        url_api = 'https://interface.bilibili.com/v2/playurl?%s&sign=%s' % (params, chksum)
        headers = {
            'Referer': start_url,  # 注意加上referer
            'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/55.0.2883.87 Safari/537.36'
        }
        # print(url_api)
        html = requests.get(url_api, headers=headers).json()
        # print(json.dumps(html))
        video_list = []
        for i in html['durl']:
            video_list.append(i['url'])
        # print(video_list)
        return video_list

    def down_video(self, video_list, title, start_url, page):
        num = 1
        print('[正在下载P{}段视频,请稍等...]:'.format(page) + title)
        currentVideoPath = os.path.join(sys.path[0], 'bilibili_video', title)  # 当前目录作为下载目录
        if not os.path.exists(currentVideoPath):
            os.makedirs(currentVideoPath)
        for i in video_list:
            opener = urllib.request.build_opener()
            # 请求头
            opener.addheaders = [
                # ('Host', 'upos-hz-mirrorks3.acgvideo.com'),  #注意修改host,不用也行
                ('User-Agent', 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.13; rv:56.0) Gecko/20100101 Firefox/56.0'),
                ('Accept', '*/*'),
                ('Accept-Language', 'en-US,en;q=0.5'),
                ('Accept-Encoding', 'gzip, deflate, br'),
                ('Range', 'bytes=0-'),  # Range 的值要为 bytes=0- 才能下载完整视频
                ('Referer', start_url),  # 注意修改referer,必须要加的!
                ('Origin', 'https://www.bilibili.com'),
                ('Connection', 'keep-alive'),
            ]
            urllib.request.install_opener(opener)
            # 创建文件夹存放下载的视频
            if not os.path.exists(currentVideoPath):
                os.makedirs(currentVideoPath)
            # 开始下载
            if len(video_list) > 1:
                urllib.request.urlretrieve(url=i,
                                           filename=os.path.join(currentVideoPath, r'{}-{}.flv'.format(title, num)),
                                           reporthook=self.reportProgress)  # 写成mp4也行  title + '-' + num + '.flv'
            else:
                urllib.request.urlretrieve(url=i, filename=os.path.join(currentVideoPath, r'{}.flv'.format(title)),
                                           reporthook=self.reportProgress)  # 写成mp4也行  title + '-' + num + '.flv'
            num += 1

    def format_size(self, bytes):
        try:
            bytes = float(bytes)
            kb = bytes / 1024
        except:
            print("传入的字节格式不对")
            return "Error"
        if kb >= 1024:
            M = kb / 1024
            if M >= 1024:
                G = M / 1024
                return "%.3fG" % (G)
            else:
                return "%.3fM" % (M)
        else:
            return "%.3fK" % (kb)

    def reportProgress(self, blocknum, blocksize, totalsize):
        cid = threading.current_thread().getName()
        self.sigDownPercentage.emit(cid,  blocknum * blocksize / totalsize * 100)


    def prepareThreads(self, cid_list):
        title_list = []
        self.threadpool = {}
        total_count = len(cid_list)
        finished_count = 0
        for item in cid_list:
            cid = str(item['cid'])
            title = item['part']
            title = re.sub(r'[\/\\:*?"<>|]', '', title)  # 替换为空的
            print('[下载视频的cid]:' + cid)
            print('[下载视频的标题]:' + title)
            title_list.append(title)
            page = str(item['page'])
            start_url = self.start_url + "/?p=" + page
            video_list = self.get_play_list(start_url, cid, 80)
            # down_video(video_list, title, start_url, page)
            # 定义线程
            th = threading.Thread(target=self.down_video, args=(video_list, title, start_url, page))
            th.setName(cid)
            # 将线程加入线程池
            self.threadpool[cid] = [th, title, start_url]
            finished_count += 1
            self.sigPercentage.emit(int(finished_count/total_count*100))
        self.sigThreadPool.emit(self.threadpool)
        # self.sigTitleList.emit(title_list)


class AppMain(QMainWindow, Ui_MainWindow):

    sigParse = pyqtSignal(list)
    def __init__(self):
        super(QMainWindow, self).__init__()
        self.setupUi(self)
        self.show()
        self.pushButton_search.clicked.connect(self.getStartUrl)
        self.start_url = None
        self.title_list = []
        self.threadpool = {}
        self.workerThread = QThread()
        self.worker = CidParser()
        self.worker.moveToThread(self.workerThread)
        # self.workerThread.finished.connect(self.worker.deleteLater)
        self.worker.sigTitleList.connect(self.applyTitleList)
        self.worker.sigThreadPool.connect(self.applyThreadPool)
        self.worker.sigPercentage.connect(self.showStatusPercentage)
        self.worker.sigDownPercentage.connect(self.refreshProgressBar)
        self.sigParse.connect(self.worker.prepareThreads)
        self.workerThread.start()

    def refreshProgressBar(self, cid, percentage):
        pgbar = self.findChild(QProgressBar, "{}_pgbar".format(cid))
        if pgbar is not None:
            pgbar.setValue(percentage)


    def applyTitleList(self, title_list):
        self.title_list = title_list

    def applyThreadPool(self, threadpool):
        self.threadpool = threadpool
        self.tableWidget_result.clearContents()
        self.tableWidget_result.setColumnCount(3)
        self.tableWidget_result.setHorizontalHeaderLabels(['cid', '名称', ''])
        self.tableWidget_result.setRowCount(len(self.threadpool))
        self.tableWidget_result.setBGColor(QColor(193,210,240))
        rowcount = 0
        for th in self.threadpool:
            data = self.threadpool[th]
            item0 = QTableWidgetItem(data[0].getName())
            item1 = QTableWidgetItem(data[1])
            item2 = QPushButton()
            item2.setText("下载")
            item2.setObjectName(data[0].getName()+"_pbtn")
            item2.clicked.connect(self.downVideo)
            item0.setFlags(QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled)
            item1.setFlags(QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled)
            self.tableWidget_result.setItem(rowcount, 0, item0)
            self.tableWidget_result.setItem(rowcount, 1, item1)
            if self.findChild(QProgressBar, "{}_pgbar".format(data[0].getName())) is None:
                self.tableWidget_result.setCellWidget(rowcount, 2, item2)
            else:
                self.tableWidget_result.setItem(rowcount, 2 , QTableWidgetItem("下载中"))
            rowcount += 1
        self.tabWidget.setTabText(2,"搜索结果({})".format(rowcount))
        self.tabWidget.setCurrentIndex(2)

    def downVideo(self):
        cid = self.sender().objectName().split('_')[0]
        print(cid)
        self.tableWidget_download.setColumnCount(3)
        self.tableWidget_download.setHorizontalHeaderLabels(['cid', '名称', ''])
        data = self.threadpool[cid]
        print(data)
        rowcount = self.tableWidget_download.rowCount()
        self.tableWidget_download.setRowCount(rowcount+1)
        self.tableWidget_download.setBGColor(QColor(193,210,240))
        item0 = QTableWidgetItem(data[0].getName())
        item1 = QTableWidgetItem(data[1])
        item2 = QProgressBar()
        item2.setValue(0)
        item2.setObjectName(data[0].getName()+"_pgbar")
        item0.setFlags(QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled)
        item1.setFlags(QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled)
        self.tableWidget_download.setItem(rowcount, 0, item0)
        self.tableWidget_download.setItem(rowcount, 1, item1)
        self.tableWidget_download.setCellWidget(rowcount, 2, item2)
        self.tabWidget.setTabText(0,"下载中({})".format(self.tableWidget_download.rowCount()))
        self.worker.download(cid)
        # self.tabWidget.setCurrentIndex(0)
        for i in range(self.tableWidget_result.rowCount()):
            cid_row = self.tableWidget_result.item(i, 0).text()
            if cid_row == cid:
                self.tableWidget_result.clearFocus()
                self.tableWidget_result.removeRow(i)
                break
        self.tabWidget.setTabText(2,"搜索结果({})".format(self.tableWidget_result.rowCount()))



    def showStatusPercentage(self, percentage):
        self.progressBar_status.setValue(percentage)
        if percentage == 100:
            self.label_status.setText("准备就绪")

    def getStartUrl(self):
        t0 = time.time()
        input_text = self.lineEdit.text()
        try:
            if input_text.isdigit() == True:  # 如果输入的是av号
                # 获取cid的api, 传入aid即可
                self.start_url = 'https://api.bilibili.com/x/web-interface/view?aid=' + input_text
                self.worker.setUrl(self.start_url)
            else:
                self.start_url = 'https://api.bilibili.com/x/web-interface/view?aid=' + re.search(r'/av(\d+)/*', input_text).group(1)
                self.worker.setUrl(self.start_url)
        except AttributeError:
            print("请输入正确的av号！")
            return
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/55.0.2883.87 Safari/537.36'
        }
        html = requests.get(self.start_url, headers=headers).json()
        data = html['data']
        cid_list = []
        t1 = time.time()
        print(t1 - t0)
        if '?p=' in input_text:
            # 单独下载分P视频中的一集
            p = re.search(r'\?p=(\d+)', input_text).group(1)
            cid_list.append(data['pages'][int(p) - 1])
        else:
            # 如果p不存在就是全集下载
            cid_list = data['pages']
        title_list = []
        # print(cid_list)
        self.label_status.setText("解析中")
        self.progressBar_status.setValue(0)
        self.sigParse.emit(cid_list)
        # t2 = time.time()
        # print(t2 - t1)
        # for th in self.threadpool:
        #     pass
            # th.start()
            # 等待所有线程运行完毕
        # for th in self.threadpool:
        #     th.join()





    def showResult(self, start_url):
        entropy = 'rbMCKn@KuamXWlPMoJGsKcbiJKUfkPF_8dABscJntvqhRSETg'
        appkey, sec = ''.join([chr(ord(i) + 2) for i in entropy[::-1]]).split(':')
        params = 'appkey=%s&cid=%s&otype=json&qn=%s&quality=%s&type=' % (appkey, cid, quality, quality)
        chksum = hashlib.md5(bytes(params + sec, 'utf8')).hexdigest()
        url_api = 'https://interface.bilibili.com/v2/playurl?%s&sign=%s' % (params, chksum)
        headers = {
            'Referer': start_url,  # 注意加上referer
            'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/55.0.2883.87 Safari/537.36'
        }
        # print(url_api)
        html = requests.get(url_api, headers=headers).json()
        # print(json.dumps(html))
        video_list = []
        for i in html['durl']:
            video_list.append(i['url'])
        # print(video_list)
        return video_list


def main():
    QApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling)
    app= QApplication(sys.argv)
    # 加载UI
    file = QFile("./dark.qss")
    file.open(QFile.ReadOnly | QFile.Text)
    stream = QTextStream(file)
    qss = stream.readAll()
    # app.setStyleSheet(qss)
    # Ui
    mainwindow = AppMain()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()

