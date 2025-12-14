# HunyuanocrRAG
这是一款基于OCR提取信息的RAG系统，能够帮助用户快速完成信息的查询和文件匹配，减少人工核对的压力。  
<div align="center">
  <img width="397" height="291" alt="图片" src="https://github.com/user-attachments/assets/aeeaa808-f731-4b08-804c-a25500980c6a" />  
  <br>
  <img width="472" height="453" alt="图片" src="https://github.com/user-attachments/assets/ab26dc62-9bcb-4923-b20f-4cd0bfa56546" />
</div>  
## 1数据集介绍  
个人信息的文件夹里面是个人相关的证件和签署的文件：  
<img width="871" height="460" alt="图片" src="https://github.com/user-attachments/assets/a1f4678b-ae31-4590-aa4b-e83c47189884" />  
## 2功能展示  
首先用户需要选择文件夹上传信息：  
<img width="1105" height="647" alt="图片" src="https://github.com/user-attachments/assets/3b71b539-c5a7-4b99-a5f5-e3fa03153701" />  
上传之后，服务器端会保存为.pkl以及向量化.bin文件，这样你就会拥有自己的数据库，涵盖查看，增加和删除的功能：  
<img width="1449" height="859" alt="图片" src="https://github.com/user-attachments/assets/c659dccb-81bc-4c61-8e97-f774041e1aee" />  
然后就可以询问任何你想要询问或者审查的任务：  
<img width="1471" height="773" alt="图片" src="https://github.com/user-attachments/assets/d017ec5a-7c5b-45f7-abcb-71d8d0a53118" />
## 3快速启动  
设置好自己的OCR模型，embedding和LLM的参数，然后运行start.sh脚本即可运行。  
<img width="989" height="487" alt="图片" src="https://github.com/user-attachments/assets/6b82ef73-f6be-4d15-b6ea-efda0a65cfd9" />

